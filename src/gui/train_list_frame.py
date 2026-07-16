import tkinter as tk
from tkinter import ttk


class TrainListFrame(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="검색 결과")
        self.trains = []

        top = ttk.Frame(self)
        top.pack(fill="x", padx=5, pady=(5, 0))
        self.select_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="전체선택/해제", variable=self.select_all_var,
                        command=self._toggle_all).pack(side="left")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("select", "train_no", "dep", "arr", "dep_time", "arr_time", "general", "special")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=6)
        headers = [("select", "선택", 40), ("train_no", "열차번호", 70),
                   ("dep", "출발역", 70), ("arr", "도착역", 70),
                   ("dep_time", "출발", 60), ("arr_time", "도착", 60),
                   ("general", "일반석", 70), ("special", "특실", 70)]
        for key, text, width in headers:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="center")

        self.tree.tag_configure("available", foreground="#1a7f37")
        self.tree.tag_configure("soldout", foreground="#888888")

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<ButtonRelease-1>", self._on_click)

        self.selected_indices = set()

    def set_trains(self, trains: list, time_to: str = "230000"):
        self.trains = []
        self.selected_indices.clear()
        self.select_all_var.set(False)
        for item in self.tree.get_children():
            self.tree.delete(item)

        for t in trains:
            dep_time = getattr(t, "dep_time", "")
            if dep_time > time_to:
                continue
            self.trains.append(t)
            train_no = getattr(t, "train_number", "")
            dep = getattr(t, "dep_station_name", "")
            arr = getattr(t, "arr_station_name", "")
            arr_time = getattr(t, "arr_time", "")
            general = getattr(t, "general_seat_state", "")
            special = getattr(t, "special_seat_state", "")
            fmt_dep = f"{dep_time[:2]}:{dep_time[2:4]}" if len(dep_time) >= 4 else dep_time
            fmt_arr = f"{arr_time[:2]}:{arr_time[2:4]}" if len(arr_time) >= 4 else arr_time
            tag = "available" if "가능" in str(general) else "soldout"
            self.tree.insert("", "end", iid=str(len(self.trains) - 1),
                             values=("", train_no, dep, arr, fmt_dep, fmt_arr, general, special),
                             tags=(tag,))

    def _toggle_all(self):
        select = self.select_all_var.get()
        self.selected_indices = set(range(len(self.trains))) if select else set()
        for i in range(len(self.trains)):
            self.tree.set(str(i), "select", "✓" if select else "")

    def _on_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        idx = int(item)
        if idx in self.selected_indices:
            self.selected_indices.discard(idx)
            self.tree.set(item, "select", "")
        else:
            self.selected_indices.add(idx)
            self.tree.set(item, "select", "✓")

    def get_selected_trains(self) -> list:
        return [self.trains[i] for i in sorted(self.selected_indices) if i < len(self.trains)]
