import tkinter as tk
from tkinter import ttk


class ReserveFrame(ttk.LabelFrame):
    def __init__(self, parent, on_start, on_stop):
        super().__init__(parent, text="예매 설정")
        self.on_start = on_start
        self.on_stop = on_stop

        row = ttk.Frame(self)
        row.pack(fill="x", padx=5, pady=5)
        ttk.Label(row, text="재시도 간격:").pack(side="left")
        self.interval_var = tk.DoubleVar(value=0.8)
        ttk.Entry(row, textvariable=self.interval_var, width=5).pack(side="left", padx=(2, 2))
        ttk.Label(row, text="초").pack(side="left", padx=(0, 15))
        ttk.Label(row, text="Discord:").pack(side="left")
        self.webhook_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.webhook_var, width=30).pack(
            side="left", padx=2, fill="x", expand=True)

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=5, pady=(0, 5))
        self.start_btn = ttk.Button(btn_row, text="예매 시작", command=self.on_start)
        self.start_btn.pack(side="left", padx=5)
        self.stop_btn = ttk.Button(btn_row, text="중지", command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(btn_row, textvariable=self.status_var).pack(side="right", padx=5)

    def set_running(self, running: bool):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")
        if not running:
            self.status_var.set("대기 중")

    def set_status(self, attempt: int, elapsed: float):
        m, s = divmod(int(elapsed), 60)
        self.status_var.set(f"시도 #{attempt}  경과 {m:02d}:{s:02d}")

    def load_config(self, cfg: dict):
        self.interval_var.set(cfg.get("retry_interval", 0.8))
        self.webhook_var.set(cfg.get("discord_webhook", ""))

    def get_config(self) -> dict:
        return {
            "retry_interval": self.interval_var.get(),
            "discord_webhook": self.webhook_var.get().strip(),
        }
