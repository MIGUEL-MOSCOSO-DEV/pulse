import csv
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .metrics import Alerts, History, sample
from .paths import data_dir
from .ui import Tasks, table, theme


class Pulse:
    def __init__(self, root):
        self.root = root
        root.title("Pulse — Monitor del equipo")
        root.geometry("1080x740")
        theme(root, "#101820", "#e6eef2", "#7edbd1")
        self.history = History(data_dir() / "metrics.sqlite")
        self.alerts = Alerts()
        self.tasks = Tasks(root)
        self.commands = queue.Queue()
        self.tray = None
        self.thresholds = {"cpu": 90, "ram": 90, "disk": 95}
        self.metrics = {}
        self.paused = True
        header = ttk.Frame(root, padding=24)
        header.pack(fill="x")
        ttk.Label(header, text="PULSE   /   SYSTEM TELEMETRY", style="Sub.TLabel").pack(anchor="w")
        ttk.Label(header, text="El pulso de tu equipo.", style="Title.TLabel").pack(
            side="left", pady=10
        )
        ttk.Button(header, text="Umbrales", command=self.settings).pack(side="right", padx=6)
        ttk.Button(header, text="Exportar historial", command=self.export).pack(
            side="right", padx=6
        )
        strip = ttk.Frame(root, padding=(24, 0))
        strip.pack(fill="x")
        for label in ["CPU", "RAM", "DISCO"]:
            block = ttk.Frame(strip, padding=20)
            block.pack(side="left", fill="x", expand=True)
            ttk.Label(block, text=label, style="Sub.TLabel").pack(anchor="w")
            value = tk.StringVar(value="—")
            self.metrics[label] = value
            ttk.Label(block, textvariable=value, font=("Consolas", 32)).pack(anchor="w")
        self.canvas = tk.Canvas(root, height=160, bg="#14232e", highlightthickness=0)
        self.canvas.pack(fill="x", padx=24, pady=16)
        bottom = ttk.Frame(root, padding=(24, 0))
        bottom.pack(fill="both", expand=True)
        ttk.Label(bottom, text="PROCESOS / MAYOR MEMORIA RESIDENTE", style="Sub.TLabel").pack(
            anchor="w"
        )
        self.tree = table(bottom, ("PID", "Proceso", "Memoria"), (100, 540, 160))
        self.status = tk.StringVar(
            value="Monitoreo detenido. Pulsa Iniciar para tomar medidas del equipo."
        )
        footer = ttk.Frame(root, padding=16)
        footer.pack(side="bottom", fill="x", before=strip)
        ttk.Label(footer, textvariable=self.status).pack(side="left")
        self.toggle = ttk.Button(footer, text="Iniciar monitoreo", command=self.toggle_monitor)
        self.toggle.pack(side="right", padx=5)
        ttk.Button(footer, text="Bandeja", command=self.hide).pack(side="right", padx=5)
        ttk.Button(footer, text="Salir", command=self.quit).pack(side="right", padx=5)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.after(200, self.update)
        root.after(200, self.poll)

    def toggle_monitor(self):
        self.paused = not self.paused
        self.toggle.configure(text="Iniciar monitoreo" if self.paused else "Pausar")
        self.status.set("Monitoreo detenido." if self.paused else "Tomando medidas…")

    def update(self):
        if self.paused:
            self.root.after(2000, self.update)
            return

        def collect():
            item = sample()
            self.history.add(item)
            return item, self.history.rows()

        self.tasks.run(collect, self.render)
        self.root.after(2000, self.update)

    def render(self, result):
        item, rows = result
        for label, metric in [("CPU", "cpu"), ("RAM", "ram"), ("DISCO", "disk")]:
            self.metrics[label].set(f"{item[metric]:.1f}%")
        self.tree.delete(*self.tree.get_children())
        for pid, name, size in item["processes"]:
            self.tree.insert("", "end", values=(pid, name, f"{size / 1024**2:.1f} MB"))
        self.canvas.delete("all")
        width, height = self.canvas.winfo_width(), 160
        for value in [25, 50, 75]:
            self.canvas.create_line(
                0, height - value * 1.4, width, height - value * 1.4, fill="#29404e"
            )
        for column, color in [(1, "#7edbd1"), (2, "#c9a5ff")]:
            points = []
            for i, row in enumerate(rows):
                points.extend(
                    (i * width / max(119, len(rows) - 1), height - 12 - row[column] * 1.35)
                )
            if len(points) >= 4:
                self.canvas.create_line(*points, fill=color, width=2)
        self.canvas.create_text(
            12,
            12,
            anchor="nw",
            text="CPU  /  RAM      últimas 120 muestras",
            fill="#c9dce5",
            font=("Consolas", 10),
        )
        alerts = self.alerts.evaluate(item, self.thresholds)
        self.status.set(
            " · ".join(alerts)
            if alerts
            else f"Memoria: {item['used'] / 1024**3:.1f} / {item['total'] / 1024**3:.1f} GB · Muestreo cada 2 s"
        )
        if alerts and self.tray:
            self.tray.notify("\n".join(alerts), "Pulse")

    def settings(self):
        from tkinter.simpledialog import askinteger

        for key in self.thresholds:
            value = askinteger(
                "Umbral de " + key.upper(),
                "Porcentaje (1–100)",
                initialvalue=self.thresholds[key],
                minvalue=1,
                maxvalue=100,
                parent=self.root,
            )
            if value is not None:
                self.thresholds[key] = value

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["unix_time", "cpu_percent", "ram_percent", "disk_percent"])
                writer.writerows(self.history.rows(50000))
            self.status.set("Historial exportado.")

    def hide(self):
        if not self.tray:
            try:
                import pystray
                from PIL import Image, ImageDraw

                image = Image.new("RGB", (64, 64), "#101820")
                ImageDraw.Draw(image).line(
                    [(8, 36), (20, 36), (26, 15), (35, 49), (43, 28), (56, 28)],
                    fill="#7edbd1",
                    width=5,
                )
                self.tray = pystray.Icon(
                    "Pulse",
                    image,
                    "Pulse",
                    pystray.Menu(
                        pystray.MenuItem(
                            "Mostrar", lambda *_: self.commands.put("show"), default=True
                        ),
                        pystray.MenuItem("Salir", lambda *_: self.commands.put("quit")),
                    ),
                )
                self.tray.run_detached()
            except Exception as error:
                self.tray = None
                messagebox.showerror("Bandeja no disponible", str(error))
                return
        self.root.withdraw()

    def poll(self):
        while not self.commands.empty():
            command = self.commands.get()
            if command == "show":
                self.root.deiconify()
            elif command == "quit":
                self.quit()
                return
        self.root.after(200, self.poll)

    def quit(self):
        if self.tray:
            self.tray.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    Pulse(root)
    root.mainloop()
