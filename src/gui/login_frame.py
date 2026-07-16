import tkinter as tk
from tkinter import ttk
import webbrowser


class LoginFrame(ttk.LabelFrame):
    def __init__(self, parent, manager, on_login):
        super().__init__(parent, text="로그인")
        self.manager = manager
        self.on_login = on_login

        row = ttk.Frame(self)
        row.pack(fill="x", padx=5, pady=5)
        ttk.Label(row, text="ID:").pack(side="left")
        self.id_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.id_var, width=16).pack(side="left", padx=(2, 10))
        ttk.Label(row, text="PW:").pack(side="left")
        self.pw_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.pw_var, width=16, show="*").pack(side="left", padx=(2, 10))
        self.login_btn = ttk.Button(row, text="로그인", command=self._do_login)
        self.login_btn.pack(side="left", padx=5)

        link_row = ttk.Frame(self)
        link_row.pack(fill="x", padx=5)
        self.status_var = tk.StringVar(value="상태: 로그인 전")
        ttk.Label(link_row, textvariable=self.status_var).pack(side="left")
        ttk.Button(link_row, text="회원번호 찾기",
                   command=lambda: webbrowser.open(self.manager.find_id_url)).pack(side="right", padx=(5, 0))
        ttk.Button(link_row, text="비밀번호 찾기",
                   command=lambda: webbrowser.open(self.manager.find_pw_url)).pack(side="right", padx=(5, 0))

    def _do_login(self):
        self.login_btn.configure(state="disabled")
        self.status_var.set("상태: 로그인 중...")
        self.update_idletasks()
        self.on_login(self.id_var.get().strip(), self.pw_var.get().strip())

    def set_status(self, msg: str, success: bool = True):
        self.status_var.set(f"상태: {msg}")
        self.login_btn.configure(state="disabled" if success else "normal")

    def load_config(self, cfg: dict):
        self.id_var.set(cfg.get("srt_id", ""))
        self.pw_var.set(cfg.get("password", ""))
