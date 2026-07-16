import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue

import sv_ttk

from src.gui.login_frame import LoginFrame
from src.gui.search_frame import SearchFrame
from src.gui.train_list_frame import TrainListFrame
from src.gui.reserve_frame import ReserveFrame
from src.gui.log_frame import LogFrame
from src.core.reservation_worker import ReservationWorker
from src.config.settings import load_config, save_config


class App:
    def __init__(self, manager):
        self.manager = manager
        self.rail = manager.name.lower()
        self.root = tk.Tk()
        self.root.title(f"{manager.name} 예약 매크로 v1.1")
        self.root.geometry("640x800")
        self.root.resizable(False, False)
        sv_ttk.set_theme("light")

        self.worker = None
        self.log_queue = queue.Queue()
        self.cfg = load_config(self.rail)

        self._build_ui()
        self._load_config()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        pad = {"padx": 10, "pady": (5, 0), "sticky": "ew"}
        self.login_frame = LoginFrame(self.root, self.manager, on_login=self._on_login)
        self.login_frame.grid(row=0, column=0, **pad)
        self.search_frame = SearchFrame(self.root, self.manager, on_search=self._on_search)
        self.search_frame.grid(row=1, column=0, **pad)
        self.train_frame = TrainListFrame(self.root)
        self.train_frame.grid(row=2, column=0, **pad)
        self.reserve_frame = ReserveFrame(self.root, on_start=self._on_reserve_start,
                                          on_stop=self._on_reserve_stop)
        self.reserve_frame.grid(row=3, column=0, **pad)
        self.log_frame = LogFrame(self.root)
        self.log_frame.grid(row=4, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(4, weight=1)

    def _load_config(self):
        self.login_frame.load_config(self.cfg)
        self.search_frame.load_config(self.cfg)
        self.reserve_frame.load_config(self.cfg)

    def _save_config(self):
        cfg = {**self.cfg}
        cfg["srt_id"] = self.login_frame.id_var.get().strip()
        cfg["password"] = self.login_frame.pw_var.get()
        cfg.update(self.search_frame.get_config())
        cfg.update(self.reserve_frame.get_config())
        save_config(cfg, self.rail)

    def _on_login(self, user_id: str, password: str):
        def do():
            ok, msg = self.manager.login(user_id, password)
            self.root.after(0, lambda: self._login_done(ok, msg))
        threading.Thread(target=do, daemon=True).start()

    def _login_done(self, ok: bool, msg: str):
        self.login_frame.set_status(msg, success=ok)
        self.log_frame.append("로그인 성공" if ok else f"로그인 실패: {msg}")

    def _on_search(self, params: dict):
        if not self.manager.logged_in:
            messagebox.showwarning("경고", "먼저 로그인해주세요.")
            self.search_frame.enable_search()
            return

        def do():
            ok, result = self.manager.search(
                params["dep"], params["arr"], params["date"], params["time_from"])
            self.root.after(0, lambda: self._search_done(ok, result, params.get("time_to", "230000")))
        threading.Thread(target=do, daemon=True).start()

    def _search_done(self, ok: bool, result, time_to: str):
        self.search_frame.enable_search()
        if ok:
            self.train_frame.set_trains(result, time_to)
            self.log_frame.append(f"검색 완료: {len(self.train_frame.trains)}개 열차")
        else:
            messagebox.showerror("검색 실패", str(result))
            self.log_frame.append(f"검색 실패: {result}")

    def _on_reserve_start(self):
        selected = self.train_frame.get_selected_trains()
        if not selected:
            messagebox.showwarning("경고", "예매할 열차를 선택해주세요.")
            return
        if not self.manager.logged_in:
            messagebox.showwarning("경고", "먼저 로그인해주세요.")
            return

        params = self.search_frame.get_params()
        rcfg = self.reserve_frame.get_config()
        self.reserve_frame.set_running(True)
        self.log_frame.clear()

        self.worker = ReservationWorker(
            manager=self.manager,
            trains=selected,
            seat_type=params["seat_type"],
            window_seat=params["window_seat"],
            passengers=params.get("passengers"),
            interval=rcfg["retry_interval"],
            discord_webhook=rcfg["discord_webhook"],
            log_queue=self.log_queue,
            on_success_callback=lambda msg: self.root.after(0, lambda: self._on_success(msg)),
            on_status_callback=lambda a, e: self.root.after(0, lambda: self.reserve_frame.set_status(a, e)),
        )
        self.worker.start()

    def _on_reserve_stop(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.reserve_frame.set_running(False)

    def _on_success(self, msg: str):
        self.reserve_frame.set_running(False)
        self.worker = None
        messagebox.showinfo("예약 성공", msg)

    def _poll_queue(self):
        while not self.log_queue.empty():
            try:
                self.log_frame.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        self.root.after(100, self._poll_queue)

    def _on_close(self):
        if self.worker:
            self.worker.stop()
        self._save_config()
        self.manager.logout()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
