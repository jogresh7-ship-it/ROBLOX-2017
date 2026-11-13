"""ROBLOX 2017 Launcher - browse the models and places in this repo and control the icon replacer."""
import json
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

BASE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
MODELS = os.path.join(BASE, "ToolboxModels")
PLACES = os.path.join(BASE, "Places")
ICONS = os.path.join(BASE, "icons")
CONFIG = os.path.join(BASE, "rohtmlconfig.json")
REPLACER = os.path.join(BASE, "rohtml_icon_replacer.py")

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None


def open_path(path):
    """Open a file/folder with its default program (Roblox Studio for .rbxm/.rbxl)."""
    try:
        if os.name == "nt":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as e:
        messagebox.showerror("Can't open", f"{path}\n\n{e}")


def list_files(folder, exts):
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder) if f.lower().endswith(exts))


def split_model(name):
    """'770 Ball 4x4x4.rbxm' -> ('770', 'Ball 4x4x4')"""
    stem = os.path.splitext(name)[0]
    m = re.match(r"(\d+)\s+(.*)", stem)
    return (m.group(1), m.group(2)) if m else ("", stem)


class FileTab(ttk.Frame):
    def __init__(self, master, folder, exts, columns, row_fn, note=""):
        super().__init__(master, padding=8)
        self.folder, self.exts, self.row_fn = folder, exts, row_fn

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(top, textvariable=self.q).pack(side="left", fill="x", expand=True, padx=6)
        self.count = ttk.Label(top)
        self.count.pack(side="right")

        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        for c in columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=80 if c == "ID" else 420, anchor="w")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, pady=6)
        sb.pack(side="left", fill="y", pady=6)
        self.tree.bind("<Double-1>", lambda e: self.open_selected())

        side = ttk.Frame(self, padding=(8, 6))
        side.pack(side="left", fill="y")
        ttk.Button(side, text="Open in Studio", command=self.open_selected).pack(fill="x")
        ttk.Button(side, text="Open folder", command=lambda: open_path(self.folder)).pack(fill="x", pady=4)
        ttk.Button(side, text="Refresh", command=self.refresh).pack(fill="x")
        if note:
            ttk.Label(side, text=note, wraplength=170, foreground="#666").pack(fill="x", pady=12)
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        q = self.q.get().lower()
        files = [f for f in list_files(self.folder, self.exts) if q in f.lower()]
        for f in files:
            self.tree.insert("", "end", iid=f, values=self.row_fn(f))
        self.count.config(text=f"{len(files)} items")

    def open_selected(self):
        sel = self.tree.selection()
        if sel:
            open_path(os.path.join(self.folder, sel[0]))


class IconTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)
        self.proc = None
        self.preview_img = None
        cfg = self.load()

        ttk.Label(self, text="Window title:").grid(row=0, column=0, sticky="w")
        self.title = tk.StringVar(value=cfg["window"].get("title", "ROBLOX"))
        ttk.Entry(self, textvariable=self.title, width=30).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(self, text="Icon:").grid(row=1, column=0, sticky="nw")
        self.icons = tk.Listbox(self, height=14, exportselection=False)
        self.icons.grid(row=1, column=1, sticky="nsw", pady=4)
        icon_files = list_files(ICONS, (".ico",))
        for i in icon_files:
            self.icons.insert("end", i)
        cur = cfg["window"].get("icon")
        if cur in icon_files:
            self.icons.selection_set(icon_files.index(cur))
        self.icons.bind("<<ListboxSelect>>", lambda e: self.preview())

        self.prev = ttk.Label(self, text="(preview needs Pillow)" if Image is None else "")
        self.prev.grid(row=1, column=2, padx=16, sticky="n")

        btns = ttk.Frame(self)
        btns.grid(row=2, column=1, columnspan=2, sticky="w", pady=8)
        ttk.Button(btns, text="Save", command=self.save).pack(side="left")
        self.run_btn = ttk.Button(btns, text="Start icon replacer", command=self.toggle)
        self.run_btn.pack(side="left", padx=6)
        self.status = ttk.Label(self, text="Replacer: stopped")
        self.status.grid(row=3, column=1, sticky="w")
        self.preview()

    def load(self):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            cfg = {}
        cfg.setdefault("window", {})
        return cfg

    def selected_icon(self):
        s = self.icons.curselection()
        return self.icons.get(s[0]) if s else None

    def preview(self):
        name = self.selected_icon()
        if not (Image and name):
            return
        try:
            img = Image.open(os.path.join(ICONS, name)).convert("RGBA").resize((96, 96))
            self.preview_img = ImageTk.PhotoImage(img)
            self.prev.config(image=self.preview_img, text="")
        except Exception:
            self.prev.config(image="", text="(no preview)")

    def save(self):
        cfg = self.load()
        cfg["window"]["title"] = self.title.get()
        if self.selected_icon():
            cfg["window"]["icon"] = self.selected_icon()
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        self.status.config(text="Saved (a running replacer picks this up automatically)")

    def toggle(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc = None
            self.run_btn.config(text="Start icon replacer")
            self.status.config(text="Replacer: stopped")
            return
        if os.name != "nt":
            messagebox.showinfo("Windows only", "The icon replacer only works on Windows.")
            return
        self.save()
        exe = os.path.join(BASE, "ROHTML - App Icon Replacer.exe")
        cmd = [exe] if os.path.exists(exe) else [sys.executable, REPLACER]
        self.proc = subprocess.Popen(cmd, cwd=BASE)
        self.run_btn.config(text="Stop icon replacer")
        self.status.config(text="Replacer: running")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def main():
    root = tk.Tk()
    root.title("ROBLOX 2017 Launcher")
    root.geometry("820x520")
    try:
        root.iconbitmap(os.path.join(ICONS, "roblox2017.ico"))
    except tk.TclError:
        pass

    ttk.Label(root, text="ROBLOX 2017 Launcher", font=("Segoe UI", 16, "bold"), padding=(10, 8)).pack(anchor="w")
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    nb.add(FileTab(nb, MODELS, (".rbxm", ".rbxmx"), ("ID", "Model"), split_model,
                   note="2004-05 toolbox models. Insert into 2007-2008 Studio first; modern Studio corrupts them."),
           text="Toolbox Models")
    nb.add(FileTab(nb, PLACES, (".rbxl", ".rbxlx"), ("Place",), lambda f: (os.path.splitext(f)[0],)),
           text="Places")
    icon_tab = IconTab(nb)
    nb.add(icon_tab, text="Icon Replacer")

    root.protocol("WM_DELETE_WINDOW", lambda: (icon_tab.stop(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
