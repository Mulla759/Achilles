"""Terminal control: raw keys in, ANSI out, on both Windows and POSIX.

Deliberately dependency-free. A resume tool that makes you `pip install textual`
before it will draw a box is a resume tool people don't run, and everything this
TUI needs — alternate screen, cursor addressing, one key at a time — is a dozen
escape sequences and two ways of reading stdin.

Windows 10 build 1511 and later understand the same sequences as everything
else, but only once `ENABLE_VIRTUAL_TERMINAL_PROCESSING` is switched on, which
`enable_ansi()` does. Anything older falls back to plain scrolling output.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass

IS_WINDOWS = os.name == "nt"

# ---------------------------------------------------------------------------
# Escape sequences
# ---------------------------------------------------------------------------

ESC = "\033"
CSI = f"{ESC}["

ALT_SCREEN_ON = f"{CSI}?1049h"
ALT_SCREEN_OFF = f"{CSI}?1049l"
CURSOR_HIDE = f"{CSI}?25l"
CURSOR_SHOW = f"{CSI}?25h"
CLEAR = f"{CSI}2J"
CLEAR_LINE = f"{CSI}2K"
RESET = f"{CSI}0m"

BOLD = f"{CSI}1m"
DIM = f"{CSI}2m"
ITALIC = f"{CSI}3m"
UNDERLINE = f"{CSI}4m"
REVERSE = f"{CSI}7m"

# The palette is deliberately tiny and semantic. The web UI's rule applies here
# too: colour is never the only signal, because plenty of terminals are
# monochrome and plenty of people are colour-blind. Every state that has a
# colour also has a glyph or a word.
FG = {
    "default": f"{CSI}39m",
    "red": f"{CSI}31m",
    "green": f"{CSI}32m",
    "yellow": f"{CSI}33m",
    "blue": f"{CSI}34m",
    "magenta": f"{CSI}35m",
    "cyan": f"{CSI}36m",
    "grey": f"{CSI}90m",
}


def sgr(text: str, *codes: str) -> str:
    return f"{''.join(codes)}{text}{RESET}" if codes else text


def move(row: int, col: int) -> str:
    """1-indexed cursor addressing, matching the ANSI convention."""
    return f"{CSI}{row};{col}H"


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

# Names the app matches on. Printable characters arrive as themselves.
UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"
ENTER, ESCAPE, TAB, SHIFT_TAB, BACKSPACE, DELETE = (
    "enter",
    "escape",
    "tab",
    "shift-tab",
    "backspace",
    "delete",
)
HOME, END, PAGE_UP, PAGE_DOWN = "home", "end", "page-up", "page-down"

_CSI_FINAL = {
    "A": UP,
    "B": DOWN,
    "C": RIGHT,
    "D": LEFT,
    "H": HOME,
    "F": END,
}
_CSI_TILDE = {
    "1": HOME,
    "3": DELETE,
    "4": END,
    "5": PAGE_UP,
    "6": PAGE_DOWN,
    "7": HOME,
    "8": END,
}
# Windows getwch() returns a lead byte then a scan code for the special keys.
_WIN_SPECIAL = {
    "H": UP,
    "P": DOWN,
    "K": LEFT,
    "M": RIGHT,
    "G": HOME,
    "O": END,
    "I": PAGE_UP,
    "Q": PAGE_DOWN,
    "S": DELETE,
}


@dataclass(frozen=True)
class Size:
    rows: int
    cols: int


def size() -> Size:
    """Terminal size, floored at something drawable.

    The floor matters: `shutil` reports 0x0 when stdout is a pipe, and every
    layout calculation downstream would divide by it.
    """
    cols, rows = shutil.get_terminal_size(fallback=(80, 24))
    return Size(rows=max(rows, 10), cols=max(cols, 40))


def enable_ansi() -> bool:
    """Turn on VT processing. Returns whether the terminal can render this UI."""
    if not sys.stdout.isatty():
        return False
    if not IS_WINDOWS:
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # -11 is STD_OUTPUT_HANDLE; 0x0004 is ENABLE_VIRTUAL_TERMINAL_PROCESSING.
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


class Keyboard:
    """One key per `read()`, blocking, in raw mode.

    POSIX needs the terminal put into cbreak so keys arrive unbuffered and
    unechoed; Windows' `msvcrt` is already unbuffered and needs no setup, which
    is why the context manager does nothing there.
    """

    def __init__(self) -> None:
        self._fd: int | None = None
        self._saved = None

    def __enter__(self) -> Keyboard:
        if not IS_WINDOWS and sys.stdin.isatty():
            import termios
            import tty

            self._fd = sys.stdin.fileno()
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._fd is not None and self._saved is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    # -- reading -----------------------------------------------------------

    def read(self) -> str:
        return self._read_windows() if IS_WINDOWS else self._read_posix()

    def _read_windows(self) -> str:
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return _WIN_SPECIAL.get(msvcrt.getwch(), "")
        if ch == "\r":
            return ENTER
        if ch == "\x1b":
            return ESCAPE
        if ch == "\t":
            return TAB
        if ch == "\x08":
            return BACKSPACE
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch

    def _read_posix(self) -> str:
        ch = sys.stdin.read(1)
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch in ("\r", "\n"):
            return ENTER
        if ch == "\t":
            return TAB
        if ch in ("\x7f", "\x08"):
            return BACKSPACE
        if ch != ESC:
            return ch

        # An escape sequence, or a bare Escape key. Distinguishing them means
        # peeking with a timeout — without it, pressing Escape hangs until the
        # next keystroke arrives.
        if not self._waiting(0.05):
            return ESCAPE
        second = sys.stdin.read(1)
        if second != "[":
            return ESCAPE
        params = ""
        while True:
            nxt = sys.stdin.read(1)
            if nxt.isdigit() or nxt == ";":
                params += nxt
                continue
            if nxt == "~":
                return _CSI_TILDE.get(params.split(";")[0], "")
            if nxt == "Z":
                return SHIFT_TAB
            return _CSI_FINAL.get(nxt, "")

    @staticmethod
    def _waiting(timeout: float) -> bool:
        import select

        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        return bool(ready)


class Screen:
    """Double-buffered painting.

    Frames are composed into a list of strings and flushed in one write. Drawing
    straight to stdout instead makes a repaint visibly tear on a slow terminal,
    and this UI repaints on a timer while the model is working.
    """

    def __init__(self) -> None:
        self.rows: list[str] = []

    def __enter__(self) -> Screen:
        sys.stdout.write(ALT_SCREEN_ON + CURSOR_HIDE + CLEAR)
        sys.stdout.flush()
        return self

    def __exit__(self, *_exc: object) -> None:
        sys.stdout.write(CURSOR_SHOW + ALT_SCREEN_OFF)
        sys.stdout.flush()

    def paint(self, lines: list[str]) -> None:
        out = [move(1, 1)]
        for i, line in enumerate(lines):
            out.append(f"{move(i + 1, 1)}{CLEAR_LINE}{line}")
        out.append(f"{CSI}J")  # clear anything below the new frame
        sys.stdout.write("".join(out))
        sys.stdout.flush()
