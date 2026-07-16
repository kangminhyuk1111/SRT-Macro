import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

HOURS = [f"{h:02d}0000" for h in range(24)]


class SearchFrame(ttk.LabelFrame):
    def __init__(self, parent, manager, on_search):
        super().__init__(parent, text="검색 조건")
        self.manager = manager
        self.on_search = on_search
        stations = manager.STATIONS

        # Row 1: stations + swap
        r1 = ttk.Frame(self)
        r1.pack(fill="x", padx=5, pady=3)
        ttk.Label(r1, text="출발역:").pack(side="left")
        self.dep_var = tk.StringVar(value=stations[0])
        ttk.Combobox(r1, textvariable=self.dep_var, values=stations,
                     width=10, state="readonly").pack(side="left", padx=(2, 4))
        ttk.Button(r1, text="⇄", width=3, command=self._swap).pack(side="left", padx=2)
        ttk.Label(r1, text="도착역:").pack(side="left", padx=(4, 0))
        self.arr_var = tk.StringVar(value=stations[1] if len(stations) > 1 else stations[0])
        ttk.Combobox(r1, textvariable=self.arr_var, values=stations,
                     width=10, state="readonly").pack(side="left", padx=2)

        # Row 2: date (+/-) + time
        r2 = ttk.Frame(self)
        r2.pack(fill="x", padx=5, pady=3)
        ttk.Label(r2, text="날짜:").pack(side="left")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        self.date_var = tk.StringVar(value=tomorrow)
        ttk.Button(r2, text="-", width=2,
                   command=lambda: self._shift_date(-1)).pack(side="left", padx=(2, 0))
        ttk.Entry(r2, textvariable=self.date_var, width=10).pack(side="left", padx=2)
        ttk.Button(r2, text="+", width=2,
                   command=lambda: self._shift_date(1)).pack(side="left", padx=(0, 15))
        ttk.Label(r2, text="시간:").pack(side="left")
        self.time_from_var = tk.StringVar(value="000000")
        ttk.Combobox(r2, textvariable=self.time_from_var, values=HOURS,
                     width=8, state="readonly").pack(side="left", padx=2)
        ttk.Label(r2, text="~").pack(side="left")
        self.time_to_var = tk.StringVar(value="230000")
        ttk.Combobox(r2, textvariable=self.time_to_var, values=HOURS,
                     width=8, state="readonly").pack(side="left", padx=2)

        # Row 3: passengers (from manager metadata)
        r3 = ttk.Frame(self)
        r3.pack(fill="x", padx=5, pady=3)
        self.pax = {}
        for label, key, default in manager.PASSENGER_TYPES:
            ttk.Label(r3, text=f"{label}:").pack(side="left")
            var = tk.IntVar(value=default)
            self.pax[key] = var
            ttk.Spinbox(r3, from_=0, to=9, textvariable=var, width=3).pack(side="left", padx=(0, 8))

        # Row 4: seat + window(optional) + search
        r4 = ttk.Frame(self)
        r4.pack(fill="x", padx=5, pady=3)
        ttk.Label(r4, text="좌석:").pack(side="left")
        self.seat_var = tk.StringVar(value=manager.SEAT_TYPES[0])
        for st in manager.SEAT_TYPES:
            ttk.Radiobutton(r4, text=st, variable=self.seat_var, value=st).pack(side="left", padx=2)

        self.window_var = tk.BooleanVar(value=False)
        if manager.supports_window_seat:
            ttk.Checkbutton(r4, text="창가석", variable=self.window_var).pack(side="left", padx=(10, 0))

        self.search_btn = ttk.Button(r4, text="검색", command=self._do_search)
        self.search_btn.pack(side="right", padx=5)

    def _swap(self):
        d, a = self.dep_var.get(), self.arr_var.get()
        self.dep_var.set(a)
        self.arr_var.set(d)

    def _shift_date(self, days: int):
        try:
            d = datetime.strptime(self.date_var.get().strip(), "%Y%m%d")
        except ValueError:
            d = datetime.now()
        self.date_var.set((d + timedelta(days=days)).strftime("%Y%m%d"))

    def _do_search(self):
        self.search_btn.configure(state="disabled")
        self.update_idletasks()
        self.on_search(self.get_params())

    def enable_search(self):
        self.search_btn.configure(state="normal")

    def get_params(self) -> dict:
        return {
            "dep": self.dep_var.get(),
            "arr": self.arr_var.get(),
            "date": self.date_var.get().strip(),
            "time_from": self.time_from_var.get(),
            "time_to": self.time_to_var.get(),
            "passengers": {k: v.get() for k, v in self.pax.items()},
            "seat_type": self.seat_var.get(),
            "window_seat": self.window_var.get(),
        }

    def load_config(self, cfg: dict):
        if cfg.get("dep_station") in self.manager.STATIONS:
            self.dep_var.set(cfg["dep_station"])
        if cfg.get("arr_station") in self.manager.STATIONS:
            self.arr_var.set(cfg["arr_station"])
        if cfg.get("date"):
            self.date_var.set(cfg["date"])
        self.time_from_var.set(cfg.get("time_from", "000000"))
        self.time_to_var.set(cfg.get("time_to", "230000"))
        for k, v in cfg.get("passengers", {}).items():
            if k in self.pax:
                self.pax[k].set(v)
        if cfg.get("seat_type") in self.manager.SEAT_TYPES:
            self.seat_var.set(cfg["seat_type"])
        self.window_var.set(cfg.get("window_seat", False))

    def get_config(self) -> dict:
        return {
            "dep_station": self.dep_var.get(),
            "arr_station": self.arr_var.get(),
            "date": self.date_var.get().strip(),
            "time_from": self.time_from_var.get(),
            "time_to": self.time_to_var.get(),
            "passengers": {k: v.get() for k, v in self.pax.items()},
            "seat_type": self.seat_var.get(),
            "window_seat": self.window_var.get(),
        }
