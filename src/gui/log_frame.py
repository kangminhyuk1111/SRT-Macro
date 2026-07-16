import tkinter as tk
from tkinter import ttk


class LogFrame(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="로그")
        self.text = tk.Text(self, height=8, state="disabled", wrap="word")
        scrollbar = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def append(self, message: str):
        self.text.configure(state="normal")
        self.text.insert("end", message + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
