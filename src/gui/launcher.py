import tkinter as tk
from tkinter import ttk

import sv_ttk


def choose_rail() -> str:
    """SRT/KTX 선택 창을 띄우고 선택값('srt'/'ktx')을 반환. 닫으면 None."""
    win = tk.Tk()
    win.title("철도 선택")
    win.geometry("320x180")
    win.resizable(False, False)
    sv_ttk.set_theme("light")

    choice = {"rail": None}

    def pick(rail):
        choice["rail"] = rail
        win.destroy()

    ttk.Label(win, text="예약할 철도를 선택하세요",
              font=("", 13)).pack(pady=(28, 18))
    btns = ttk.Frame(win)
    btns.pack()
    ttk.Button(btns, text="SRT", width=12,
               command=lambda: pick("srt")).pack(side="left", padx=8)
    ttk.Button(btns, text="KTX", width=12,
               command=lambda: pick("ktx")).pack(side="left", padx=8)

    # macOS에서 터미널로 실행 시 창을 최전면 활성 앱으로 올린다.
    win.lift()
    win.attributes("-topmost", True)
    win.after(200, lambda: win.attributes("-topmost", False))
    win.focus_force()

    win.mainloop()
    return choice["rail"]


def make_manager(rail: str):
    if rail == "ktx":
        from src.core.korail_manager import KorailManager
        return KorailManager()
    from src.core.srt_manager import SRTManager
    return SRTManager()
