"""VoicePlugin — record / attach / play back voice notes.

A voice note stores its audio inline as a base64 *data URI* string in the
note's ``content`` field, e.g.::

    data:audio/mp4;base64,AAAA....

This keeps the existing string-based note storage and encryption pipeline
unchanged — the audio rides along as ordinary (null-byte-free) text.

The editor widget (``VoiceEditorWidget``) provides:
  * a microphone recorder (QMediaCaptureSession + QMediaRecorder),
  * an "attach audio file" picker,
  * inline playback (QMediaPlayer + QAudioOutput) with a seek slider.

MIME routing
------------
The plugin advertises the routing MIME ``audio/basic`` in both
``provides_formats`` (so it appears in the New Note chooser) and
``mime_types`` (so reopened voice notes resolve back to this editor).
MainWindow maps any ``data:audio/...`` content to ``audio/basic``.
"""
from __future__ import annotations

import base64
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtMultimedia import (
    QAudioInput,
    QAudioOutput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaPlayer,
    QMediaRecorder,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.plugin_base import PluginBase, PluginRegistry
from src.core.plugin_context import PluginContext

# Routing MIME — what the host uses to pick this editor (not the stored codec).
VOICE_MIME = "audio/basic"

# Refuse to inline anything larger than this (base64 inflates ~33%, and the
# whole blob lives in the note row).  Keeps the database from ballooning.
_MAX_BYTES = 50 * 1024 * 1024  # 50 MB

# Map a file suffix to the audio MIME we record into the data URI.
_SUFFIX_MIME = {
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".aac": "audio/aac",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".flac": "audio/flac",
    ".weba": "audio/webm",
    ".webm": "audio/webm",
}


def _fmt_ms(ms: int) -> str:
    """Format a millisecond duration as ``M:SS``."""
    if ms <= 0:
        return "0:00"
    total = ms // 1000
    return f"{total // 60}:{total % 60:02d}"


class VoiceEditorWidget(QWidget):
    """EditorProtocol widget for recording and playing back a voice note."""

    save_requested = Signal(str, object)   # (title, data_uri)
    content_changed = Signal()
    delete_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._data_uri: str = ""                       # current audio, "" = none
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="astranotes_voice_"))
        self._playback_file: Optional[Path] = None
        self._recording = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Title ──────────────────────────────────────────────────────────
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Voice note title")
        self._title_edit.textChanged.connect(self.content_changed)
        layout.addWidget(self._title_edit)

        # ── Source row: record + attach ────────────────────────────────────
        source_row = QHBoxLayout()
        self._record_btn = QPushButton("⏺  Record")
        self._record_btn.setToolTip("Record from your microphone")
        self._record_btn.clicked.connect(self._on_record_clicked)
        source_row.addWidget(self._record_btn)

        self._attach_btn = QPushButton("\U0001f4ce  Attach file…")
        self._attach_btn.setToolTip("Attach an existing audio file")
        self._attach_btn.clicked.connect(self._on_attach_clicked)
        source_row.addWidget(self._attach_btn)
        source_row.addStretch(1)
        layout.addLayout(source_row)

        # ── Playback row: play/pause + seek + time ─────────────────────────
        play_row = QHBoxLayout()
        self._play_btn = QToolButton()
        self._play_btn.setText("▶")
        self._play_btn.setToolTip("Play / pause")
        self._play_btn.clicked.connect(self._on_play_clicked)
        self._play_btn.setEnabled(False)
        play_row.addWidget(self._play_btn)

        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setEnabled(False)
        self._seek.sliderMoved.connect(self._on_seek)
        play_row.addWidget(self._seek, stretch=1)

        self._time_label = QLabel("0:00 / 0:00")
        play_row.addWidget(self._time_label)
        layout.addLayout(play_row)

        # ── Status + save / delete ─────────────────────────────────────────
        self._status = QLabel("No audio yet — record or attach a file.")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #888;")
        layout.addWidget(self._status)
        layout.addStretch(1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self._save_btn = QToolButton()
        self._save_btn.setText("\U0001f4be")
        self._save_btn.setToolTip("Save  (Ctrl+S)")
        self._save_btn.clicked.connect(self._emit_save)
        action_row.addWidget(self._save_btn)
        self._delete_btn = QToolButton()
        self._delete_btn.setText("\U0001f5d1")
        self._delete_btn.setToolTip("Delete note")
        self._delete_btn.clicked.connect(self.delete_requested)
        action_row.addWidget(self._delete_btn)
        layout.addLayout(action_row)

        # ── Media objects ──────────────────────────────────────────────────
        self._player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_out)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state)

        self._capture: Optional[QMediaCaptureSession] = None
        self._audio_in: Optional[QAudioInput] = None
        self._recorder: Optional[QMediaRecorder] = None

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def _ensure_recorder(self) -> bool:
        """Lazily build the capture pipeline.  Returns False if no mic."""
        if self._recorder is not None:
            return True
        if not QMediaDevices.audioInputs():
            self._status.setText("No microphone detected.")
            return False
        self._capture = QMediaCaptureSession()
        self._audio_in = QAudioInput()
        self._capture.setAudioInput(self._audio_in)
        self._recorder = QMediaRecorder()
        fmt = QMediaFormat(QMediaFormat.FileFormat.MPEG4)
        fmt.setAudioCodec(QMediaFormat.AudioCodec.AAC)
        self._recorder.setMediaFormat(fmt)
        self._capture.setRecorder(self._recorder)
        self._recorder.recorderStateChanged.connect(self._on_recorder_state)
        self._recorder.errorOccurred.connect(self._on_recorder_error)
        return True

    def _on_record_clicked(self) -> None:
        if self._recording:
            if self._recorder is not None:
                self._recorder.stop()
            return
        if not self._ensure_recorder() or self._recorder is None:
            return
        # Stop any playback first so the device is free.
        self._player.stop()
        out = self._tmp_dir / f"rec_{uuid.uuid4().hex}.m4a"
        self._recorder.setOutputLocation(QUrl.fromLocalFile(str(out)))
        self._recorder.record()

    def _on_recorder_state(self, state: Any) -> None:
        recording = state == QMediaRecorder.RecorderState.RecordingState
        self._recording = recording
        if recording:
            self._record_btn.setText("⏹  Stop")
            self._status.setText("Recording…")
        else:
            self._record_btn.setText("⏺  Record")
            if state == QMediaRecorder.RecorderState.StoppedState:
                self._ingest_recording()

    def _on_recorder_error(self, _error: Any, error_string: str) -> None:
        self._status.setText(f"Recording error: {error_string}")
        self._recording = False
        self._record_btn.setText("⏺  Record")

    def _ingest_recording(self) -> None:
        if self._recorder is None:
            return
        loc = self._recorder.actualLocation()
        path = Path(loc.toLocalFile()) if loc.toLocalFile() else None
        if path is None or not path.exists() or path.stat().st_size == 0:
            self._status.setText("Recording produced no audio.")
            return
        raw = path.read_bytes()
        mime = _SUFFIX_MIME.get(path.suffix.lower(), "audio/mp4")
        self._set_audio(raw, mime)
        self._status.setText(f"Recorded {_fmt_ms(self._recorder.duration())} of audio.")

    # ------------------------------------------------------------------
    # Attaching a file
    # ------------------------------------------------------------------
    def _on_attach_clicked(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Attach audio file",
            "",
            "Audio (*.mp3 *.m4a *.aac *.wav *.ogg *.opus *.flac *.webm)",
        )
        if not path_str:
            return
        path = Path(path_str)
        raw = path.read_bytes()
        if len(raw) > _MAX_BYTES:
            self._status.setText(
                f"File is too large ({len(raw) // (1024 * 1024)} MB). "
                f"Limit is {_MAX_BYTES // (1024 * 1024)} MB."
            )
            return
        mime = _SUFFIX_MIME.get(path.suffix.lower(), "audio/mpeg")
        self._set_audio(raw, mime)
        self._status.setText(f"Attached “{path.name}”.")

    # ------------------------------------------------------------------
    # Audio (de)serialisation
    # ------------------------------------------------------------------
    def _set_audio(self, raw: bytes, mime: str) -> None:
        if len(raw) > _MAX_BYTES:
            self._status.setText("Audio exceeds the size limit; not stored.")
            return
        b64 = base64.b64encode(raw).decode("ascii")
        self._data_uri = f"data:{mime};base64,{b64}"
        self._load_into_player(raw, mime)
        self._play_btn.setEnabled(True)
        self._seek.setEnabled(True)
        self.content_changed.emit()

    def _load_into_player(self, raw: bytes, mime: str) -> None:
        # QMediaPlayer plays most reliably from a real file URL.
        suffix = next((s for s, m in _SUFFIX_MIME.items() if m == mime), ".m4a")
        pf = self._tmp_dir / f"play_{uuid.uuid4().hex}{suffix}"
        pf.write_bytes(raw)
        self._playback_file = pf
        self._player.setSource(QUrl.fromLocalFile(str(pf)))

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------
    def _on_play_clicked(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_playback_state(self, state: Any) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._play_btn.setText("⏸" if playing else "▶")

    def _on_seek(self, value: int) -> None:
        self._player.setPosition(value)

    def _on_position_changed(self, pos: int) -> None:
        if not self._seek.isSliderDown():
            self._seek.setValue(pos)
        self._time_label.setText(f"{_fmt_ms(pos)} / {_fmt_ms(self._player.duration())}")

    def _on_duration_changed(self, dur: int) -> None:
        self._seek.setRange(0, dur)
        self._time_label.setText(f"{_fmt_ms(self._player.position())} / {_fmt_ms(dur)}")

    # ------------------------------------------------------------------
    # EditorProtocol interface
    # ------------------------------------------------------------------
    def as_widget(self) -> QWidget:
        return self

    def load(self, title: str, data: Any) -> None:
        self._player.stop()   # halt any playback before (re)loading or locking
        self._title_edit.blockSignals(True)
        self._title_edit.setText(str(title) if title else "")
        self._title_edit.blockSignals(False)
        text = data if isinstance(data, str) else ""
        if text.lstrip().startswith("data:audio/"):
            parsed = self._parse_data_uri(text.strip())
            if parsed is not None:
                mime, raw = parsed
                self._data_uri = text.strip()
                self._load_into_player(raw, mime)
                self._play_btn.setEnabled(True)
                self._seek.setEnabled(True)
                self._status.setText(f"Loaded audio ({len(raw) // 1024} KB).")
                return
        # No audio in this note.
        self._data_uri = ""
        self._play_btn.setEnabled(False)
        self._seek.setEnabled(False)
        self._status.setText("No audio yet — record or attach a file.")

    def show_save_result(self, ok: bool, msg: str) -> None:
        self._status.setText("Saved." if ok else f"Save failed: {msg}")

    def get_title(self) -> str:
        return self._title_edit.text().strip()

    def set_title(self, title: str) -> None:
        self._title_edit.setText(title or "")

    def get_content(self) -> str:
        return self._data_uri

    def get_html_content(self) -> str:
        return self._data_uri

    # Optional host hooks (no-ops kept signature-compatible).
    def apply_theme(self, theme: str) -> None:
        pass

    def apply_font_size(self, size: int) -> None:
        pass

    def apply_font_family(self, family: str) -> None:
        pass

    def apply_word_wrap(self, enabled: bool) -> None:
        pass

    def apply_format(self, mime: str) -> None:
        pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _emit_save(self) -> None:
        self.save_requested.emit(self.get_title(), self._data_uri)

    @staticmethod
    def _parse_data_uri(s: str) -> Optional[tuple[str, bytes]]:
        if not s.startswith("data:"):
            return None
        header, sep, payload = s.partition(",")
        if not sep or ";base64" not in header:
            return None
        mime = header[len("data:"):].split(";")[0] or "audio/mp4"
        try:
            raw = base64.b64decode(payload)
        except (ValueError, TypeError):
            return None
        return mime, raw


class VoicePlugin(PluginBase):
    """Voice-note editor plugin (microphone recording + audio file attach)."""

    name = "VoicePlugin"
    version = "1.0.0"
    mime_types = [VOICE_MIME]

    provides_formats: list[tuple[str, str, str]] = [
        (
            "Voice note",
            VOICE_MIME,
            "Record audio from your microphone or attach an audio file, "
            "then play it back inline.",
        ),
    ]

    def register_hooks(self, registry: PluginRegistry) -> None:
        pass

    def mime_type(self) -> str:
        return VOICE_MIME

    def create_editor(self) -> Optional[VoiceEditorWidget]:
        try:
            return VoiceEditorWidget()
        except Exception:
            return None

    def pack(self, data: Any) -> bytes:
        if isinstance(data, bytes):
            return data
        return str(data).encode("utf-8")

    def unpack(self, data: bytes) -> str:
        return data.decode("utf-8", errors="replace")

    def initialize(self, context: PluginContext) -> None:
        mics = len(QMediaDevices.audioInputs())
        context.log(f"VoicePlugin initialized — {mics} microphone(s) available.")
