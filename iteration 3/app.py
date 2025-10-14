##############################################################
# FOOD SUSTAINABILITY APP
# Description: A tkinter-based app for users and businesses to list, browse, and buy food items to reduce waste.
# Features:
#   - User and business login/signup
#   - Businesses can list food items
#   - Users can browse and buy food
#   - Data saved/loaded from JSON file
# Updates:
#   - Password hashing for security
#   - Improved expiry handling and migration
#   - Tabbed interface and modern UI
#   - Business notifications and withdrawal
#   - Category filtering and search
##############################################################

import tkinter as tk
from tkinter import messagebox
import datetime as dt
import json, uuid, re, threading, queue, os, hashlib, binascii

# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password, salt=None, iterations=100_000):
    """
    Hashes a password using PBKDF2 with SHA-256.
    Returns a dict with salt, hash, and iteration count.
    """
    if salt is None:
        salt = os.urandom(16)
    elif isinstance(salt, str):
        salt = binascii.unhexlify(salt)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return {"salt": binascii.hexlify(salt).decode('ascii'), "hash": binascii.hexlify(dk).decode('ascii'), "iter": iterations}

def verify_password(stored, provided):
    """
    Verifies a provided password against a stored hash dict.
    Returns True if match, False otherwise.
    """
    try:
        salt = stored['salt']
        it = stored.get('iter', 100_000)
        candidate = hash_password(provided, salt=salt, iterations=it)
        return candidate['hash'] == stored['hash']
    except Exception:
        return False

# ============================================================
# CLASSES
# ============================================================

class FoodItem:
    def __init__(self, name, category, price, business_id, expiry=None, id=None, hours=0):
        self.name = name
        self.category = category
        self.price = float(price)
        # expiry allow iso string, datetime, or calculate from hours
        if isinstance(expiry, str):
            try:
                self.expiry = dt.datetime.fromisoformat(expiry)
            except Exception:
                self.expiry = dt.datetime.now() + dt.timedelta(hours=hours)
        elif isinstance(expiry, dt.datetime):
            self.expiry = expiry
        elif expiry is None:
            self.expiry = dt.datetime.now() + dt.timedelta(hours=hours)
        else:
            self.expiry = dt.datetime.now() + dt.timedelta(hours=hours)
        self.business_id = business_id
        self.id = id if id else str(uuid.uuid4())

    def to_dict(self):
        d = self.__dict__.copy()
        d['expiry'] = self.expiry.isoformat() if isinstance(self.expiry, dt.datetime) else str(self.expiry)
        return d

class User:
    def __init__(self, username, password, name, id=None, purchases=None):
        self.username = username
        # password can be dict (hashed) or plaintext
        if isinstance(password, dict):
            self.password = password
        else:
            self.password = hash_password(password)
        self.name = name
        self.id = id if id else str(uuid.uuid4())
        self.purchases = purchases if purchases else []

    def to_dict(self):
        return {
            "username": self.username,
            "password": self.password,
            "name": self.name,
            "id": self.id,
            "purchases": [p.to_dict() for p in self.purchases]
        }

class Business:
    def __init__(self, username, password, name, id=None, listings=None, cash=0.0, notifications=None):
        self.username = username
        if isinstance(password, dict):
            self.password = password
        else:
            self.password = hash_password(password)
        self.name = name
        self.id = id if id else str(uuid.uuid4())
        self.listings = listings if listings else []
        self.cash = float(cash)
        self.notifications = notifications if notifications else []

    def to_dict(self):
        return {
            "username": self.username,
            "password": self.password,
            "name": self.name,
            "id": self.id,
            "listings": [li.to_dict() for li in self.listings],
            "cash": self.cash,
            "notifications": self.notifications
        }

# ============================================================
# SAVE AND LOAD
# ============================================================

# Always use the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
data_queue = queue.Queue()

def load_data():
    """
    Loads data from the JSON file.
    Returns a dictionary with users, businesses, and food_items lists.
    Handles blank files and missing files gracefully.
    """
    try:
        with open(DATA_FILE, "r") as f:
            txt = f.read().strip()
            if not txt:
                return {"users": [], "businesses": [], "food_items": []}
            return json.loads(txt)
    except FileNotFoundError:
        return {"users": [], "businesses": [], "food_items": []}
    except json.JSONDecodeError:
        return {"users": [], "businesses": [], "food_items": []}

def load_data_thread(q):
    q.put(load_data())

def save_data():
    """
    Removes expired food items and saves all data to JSON.
    Handles migration and serialization.
    """
    now = dt.datetime.now()
    cutoff = now - dt.timedelta(hours=24)
    global food_items
    food_items = [f for f in food_items if isinstance(f.expiry, dt.datetime) and f.expiry > cutoff]
    for b in businesses:
        b.listings = [li for li in b.listings if isinstance(li.expiry, dt.datetime) and li.expiry > cutoff]
    for u in users:
        u.purchases = [p for p in u.purchases if isinstance(p.expiry, dt.datetime) and p.expiry > cutoff]

    out = {"users": [], "businesses": [], "food_items": []}
    for u in users:
        out["users"].append(u.to_dict())
    for b in businesses:
        out["businesses"].append(b.to_dict())
    for f in food_items:
        out["food_items"].append(f.to_dict())
    with open(DATA_FILE, "w") as fh:
        json.dump(out, fh, indent=4)

# ============================================================
# GLOBALS
# ============================================================

users, businesses, food_items = [], [], []
t = threading.Thread(target=load_data_thread, args=(data_queue,))
t.start(); t.join(timeout=1)
if not data_queue.empty():
    raw = data_queue.get()
else:
    raw = {"users": [], "businesses": [], "food_items": []}

# load users
for ru in raw.get("users", []):
    purchases = []
    for p in ru.get("purchases", []):
        try:
            purchases.append(FoodItem(**p))
        except Exception:
            pass
    pwd = ru.get("password")
    if isinstance(pwd, str):
        pwd = hash_password(pwd)
    users.append(User(ru.get("username"), pwd, ru.get("name", ru.get("username")), id=ru.get("id"), purchases=purchases))

# load businesses
for rb in raw.get("businesses", []):
    listings = []
    for li in rb.get("listings", []):
        try:
            listings.append(FoodItem(**li))
        except Exception:
            pass
    pwd = rb.get("password")
    if isinstance(pwd, str):
        pwd = hash_password(pwd)
    businesses.append(Business(rb.get("username"), pwd, rb.get("name", rb.get("username")),
                               id=rb.get("id"), listings=listings, cash=rb.get("cash", 0.0),
                               notifications=rb.get("notifications", [])))

# load top-level food_items (if any)
for rf in raw.get("food_items", []):
    try:
        food_items.append(FoodItem(**rf))
    except Exception:
        pass

# save to ensure migration
save_data()

# ============================================================
# UI HELPERS
# ============================================================

def make_entry(master, **kwargs):
    e = tk.Entry(master, relief='solid', bd=1, highlightthickness=2, **kwargs)
    e.config(highlightbackground="#cfcfcf", highlightcolor="#4a90e2")
    return e

def mark_invalid(widget):
    try:
        widget.config(highlightbackground="red", highlightcolor="red")
    except Exception:
        pass

def mark_valid(widget):
    try:
        widget.config(highlightbackground="#cfcfcf", highlightcolor="#4a90e2")
    except Exception:
        pass

# ============================================================
# MAIN APP
# ============================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        # app size
        self.app_width = 420
        self.app_height = 700
        self.title("FoodFlow")
        self.geometry(f"{self.app_width}x{self.app_height}")
        self.resizable(False, False)
        # center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.app_width // 2)
        y = (self.winfo_screenheight() // 2) - (self.app_height // 2)
        self.geometry(f"+{x}+{y}")

        self.active_user = None
        self.active_business = None
        self.current_tab = "home"  # home, food, profile

        # top bar
        self.topbar = tk.Frame(self, height=64, bg="#f7f7f7")
        self.topbar.pack(fill='x')
        self.topbar.pack_propagate(False)
        self.app_label = tk.Label(self.topbar, text="FoodFlow", font=("Arial", 16, "bold"), bg="#f7f7f7")
        self.app_label.pack(side='left', padx=12)
        # profile icon area
        self.profile_btn = tk.Button(self.topbar, text="Log In", relief='flat', bg="#f7f7f7", command=self.handle_profile_click)
        self.profile_btn.pack(side='right', padx=12)

        # main content area
        self.container = tk.Frame(self, bg="#ffffff")
        self.container.pack(fill='both', expand=True, padx=8, pady=(8,4))

        # bottom nav
        self.bottom = tk.Frame(self, height=64, bg="#f0f0f0")
        self.bottom.pack(fill='x')
        self.bottom.pack_propagate(False)
        self.home_btn = tk.Button(self.bottom, text="Home", command=lambda: self.switch_tab("home"), width=14)
        self.food_btn = tk.Button(self.bottom, text="Food", command=lambda: self.switch_tab("food"), width=14)
        self.profile_tab_btn = tk.Button(self.bottom, text="Profile", command=lambda: self.switch_tab("profile"), width=14)
        self.home_btn.pack(side='left', padx=6, pady=12)
        self.food_btn.pack(side='left', padx=6, pady=12)
        self.profile_tab_btn.pack(side='left', padx=6, pady=12)

        # frames for tabs
        self.frames = {}
        for name in ("home", "food", "profile"):
            frame = tk.Frame(self.container, bg="#ffffff")
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.frames[name] = frame

        self.build_home_tab()
        self.build_food_tab()
        self.build_profile_tab()

        self.switch_tab("home")
        self.refresh_profile_btn()

    # profile actions
    def refresh_profile_btn(self):
        if self.active_user:
            # show initial
            initial = (self.active_user.name.strip()[0] if self.active_user.name else self.active_user.username[0]).upper()
            self.profile_btn.config(text=initial, command=self.open_user_menu)
        elif self.active_business:
            initial = (self.active_business.name.strip()[0] if self.active_business.name else self.active_business.username[0]).upper()
            self.profile_btn.config(text=initial, command=self.open_business_menu)
        else:
            self.profile_btn.config(text="Log In", command=self.handle_profile_click)

    def handle_profile_click(self):
        # if not logged in, open login/signup modal
        if not self.active_user and not self.active_business:
            self.open_login_choice()
        else:
            # if logged in show a quick menu
            if self.active_user:
                self.open_user_menu()
            else:
                self.open_business_menu()

    # Tabs
    def switch_tab(self, name):
        self.current_tab = name
        for n, f in self.frames.items():
            f.lift() if n == name else f.lower()
        # update content on switch
        if name == "home":
            self.populate_home()
        elif name == "food":
            self.populate_food()
        elif name == "profile":
            self.populate_profile()

    # Home tab
    def build_home_tab(self):
        f = self.frames["home"]
        tk.Label(f, text="Recommended", font=("Arial", 14, "bold"), bg="#ffffff").pack(anchor='w', padx=12, pady=(12,4))
        self.rec_canvas = tk.Canvas(f, bg="#ffffff", highlightthickness=0)
        self.rec_canvas.config(height=180)
        self.rec_canvas.pack(fill='both', expand=False, padx=12, pady=(0,6), ipady=4)
        self.rec_scroll = tk.Scrollbar(f, orient='vertical', command=self.rec_canvas.yview)
        self.rec_scroll.place(relx=0.96, rely=0.06, relheight=0.25)
        self.rec_canvas.configure(yscrollcommand=self.rec_scroll.set)
        self.rec_inner = tk.Frame(self.rec_canvas, bg="#ffffff")
        self.rec_canvas.create_window((0, 0), window=self.rec_inner, anchor='nw')
        self.rec_inner.bind("<Configure>", lambda e: self.rec_canvas.configure(scrollregion=self.rec_canvas.bbox("all")))

        # quick action
        tk.Button(f, text="View all food", width=20, command=lambda: self.switch_tab("food")).pack(pady=(6,0))

        # small recent activity
        tk.Label(f, text="Recent activity", font=("Arial", 12, "bold"), bg="#ffffff").pack(anchor='w', padx=12, pady=(12,0))
        self.activity_box = tk.Listbox(f, height=6)
        self.activity_box.pack(fill='both', padx=12, pady=6, expand=True)

    def populate_home(self):
        # recommend soonest expiry but not expired
        for w in self.rec_inner.winfo_children():
            w.destroy()
        now = dt.datetime.now()
        recs = sorted([it for it in food_items if it.expiry > now], key=lambda x: (x.expiry, x.price))[:6]
        if not recs:
            tk.Label(self.rec_inner, text="No recommended items right now", bg="#ffffff").grid(row=0, column=0, columnspan=2, pady=6)
        else:
            for idx, it in enumerate(recs):
                seller = next((b.name for b in businesses if b.id == it.business_id), "Unknown")
                expiry_text = it.expiry.strftime("%Y-%m-%d %H:%M")
                card = tk.Frame(self.rec_inner, bg="#fbfbfb", relief='groove', bd=1, padx=8, pady=6)
                tk.Label(card, text=it.name, font=("Arial", 11, "bold"), bg="#fbfbfb").pack(anchor='w')
                tk.Label(card, text=f"${it.price:.2f} • {it.category} • {seller}", bg="#fbfbfb").pack(anchor='w')
                tk.Label(card, text=f"exp {expiry_text}", fg="gray", bg="#fbfbfb").pack(anchor='w')
                row = idx // 2
                col = idx % 2
                card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
                # clickable
                card.bind("<Button-1>", lambda e, item=it: self.show_item_detail(item))
                for child in card.winfo_children():
                    child.bind("<Button-1>", lambda e, item=it: self.show_item_detail(item))
            for col in range(2):
                self.rec_inner.grid_columnconfigure(col, weight=1)
            for row in range((len(recs)+1)//2):
                self.rec_inner.grid_rowconfigure(row, weight=1)
            # dynamic canvas height
            self.rec_canvas.config(height=90*((len(recs)+1)//2))
        # show recent purchases
        self.activity_box.delete(0, 'end')
        recent = []
        for u in users:
            for p in u.purchases:
                recent.append((p, u.name))
        recent_sorted = sorted(recent, key=lambda x: getattr(x[0], 'expiry', dt.datetime.min), reverse=True)[:8]
        for p, buyer in recent_sorted:
            self.activity_box.insert('end', f"{buyer} bought {p.name} • ${p.price:.2f}")

    # Food tab
    def build_food_tab(self):
        f = self.frames["food"]
        # filters area
        filter_frame = tk.Frame(f, bg="#ffffff")
        filter_frame.pack(fill='x', padx=12, pady=(12,4))
        tk.Label(filter_frame, text="Category", bg="#ffffff").grid(row=0, column=0, sticky='w')
        self.cat_var = tk.StringVar(value="All")
        self.cat_menu = tk.OptionMenu(filter_frame, self.cat_var, "All")
        self.cat_menu.grid(row=0, column=1, padx=6)
        tk.Label(filter_frame, text="Search", bg="#ffffff").grid(row=0, column=2, sticky='w', padx=(12,0))
        self.search_var = tk.StringVar()
        self.search_entry = make_entry(filter_frame, textvariable=self.search_var, width=18)
        self.search_entry.grid(row=0, column=3, padx=(6, 12), sticky='w')

        # list area
        list_frame = tk.Frame(f, bg="#ffffff")
        list_frame.pack(fill='both', expand=True, padx=12, pady=8)
        self.food_listbox = tk.Listbox(list_frame)
        self.food_listbox.pack(side='left', fill='both', expand=True)
        self.food_scroll = tk.Scrollbar(list_frame, command=self.food_listbox.yview)
        self.food_scroll.pack(side='right', fill='y')
        self.food_listbox.config(yscrollcommand=self.food_scroll.set)
        # bind selection event
        self.food_listbox.bind("<<ListboxSelect>>", self.on_food_select)

        # open button for selected
        self.open_food_btn = tk.Button(f, text="Open", state='disabled', command=self.open_selected_food)
        self.open_food_btn.pack(pady=(4, 12))

    def on_food_select(self, evt):
        sel = self.food_listbox.curselection()
        if sel and hasattr(self, "visible_items"):
            idx = sel[0] - 2  # subtract header rows
            if 0 <= idx < len(self.visible_items):
                self.open_food_btn.config(state='normal')
            else:
                self.open_food_btn.config(state='disabled')
        else:
            self.open_food_btn.config(state='disabled')

    def open_selected_food(self):
        sel = self.food_listbox.curselection()
        if sel and hasattr(self, "visible_items"):
            idx = sel[0] - 2  # subtract header rows
            if 0 <= idx < len(self.visible_items):
                item = self.visible_items[idx]
                self.show_item_detail(item)

    def populate_food(self):
        # refresh categories
        cats = sorted(set([it.category for it in food_items if it.expiry > dt.datetime.now()]))
        menu = self.cat_menu["menu"]
        menu.delete(0, 'end')
        menu.add_command(label="All", command=lambda v="All": self.cat_var.set(v))
        for c in cats:
            menu.add_command(label=c, command=lambda v=c: self.cat_var.set(v))
        # refresh list
        self._refresh_food_list()

        # trace search and cat changes
        self.cat_var.trace('w', lambda *a: self._refresh_food_list())
        self.search_var.trace('w', lambda *a: self._refresh_food_list())

    def _refresh_food_list(self):
        self.food_listbox.delete(0, 'end')
        sel_cat = self.cat_var.get()
        q = self.search_var.get().strip().lower()
        now = dt.datetime.now()
        visible = []
        for item in food_items:
            # ensure expiry is datetime
            if not isinstance(item.expiry, dt.datetime):
                try:
                    item.expiry = dt.datetime.fromisoformat(item.expiry)
                except Exception:
                    item.expiry = dt.datetime.now()
            if item.expiry <= now:
                continue
            if sel_cat != "All" and item.category != sel_cat:
                continue
            if q and q not in item.name.lower() and q not in item.category.lower():
                continue
            visible.append(item)
        self.visible_items = visible

        # Add column headers with vertical lines
        self.food_listbox.insert('end', f"{'Name':<16}|{'Price':<8}|{'Category':<12}|{'Seller':<12}|{'Expiry':<10}")
        self.food_listbox.insert('end', "-"*60)

        for it in visible:
            seller = next((b.name for b in businesses if b.id == it.business_id), "Unknown")
            expires_in = int((it.expiry - now).total_seconds() / 3600)
            timeconst = "h"
            if expires_in == 0:
                expires_in = int((it.expiry - now).total_seconds() / 60)
                timeconst = "m"
                if expires_in == 0:
                    expires_in = int((it.expiry - now).total_seconds())
                    timeconst = "s"
            status = f"{expires_in}{timeconst} left" if expires_in > 0 else "expired"
            # Format columns with vertical lines
            self.food_listbox.insert(
                'end',
                f"{it.name:<16}|${it.price:<7.2f}|{it.category:<12}|{seller:<12}|{status:<10}"
            )

        if not visible:
            self.food_listbox.insert('end', "No items match filters")
            
    def on_food_double(self, evt):
        sel = self.food_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if not hasattr(self, "visible_items") or idx >= len(self.visible_items):
            return
        item = self.visible_items[idx]
        self.show_item_detail(item)

    def show_item_detail(self, item):
        win = tk.Toplevel(self)
        win.geometry("360x380")
        win.title(item.name)
        tk.Label(win, text=item.name, font=("Arial", 14, "bold")).pack(pady=8)
        seller = next((b.name for b in businesses if b.id == item.business_id), "Unknown")
        tk.Label(win, text=f"Seller: {seller}").pack()
        tk.Label(win, text=f"Category: {item.category}").pack()
        tk.Label(win, text=f"Price: ${item.price:.2f}").pack()
        expiry_text = item.expiry.strftime("%Y-%m-%d %H:%M")
        left_hrs = int((item.expiry - dt.datetime.now()).total_seconds() / 3600)
        timeconst = "h"
        if left_hrs == 0:
            left_hrs = int((item.expiry - dt.datetime.now()).total_seconds() / 60)
            timeconst = "m"
            if left_hrs == 0:
                left_hrs = int((item.expiry - dt.datetime.now()).total_seconds())
                timeconst = "s"
        status = f"Expires in {left_hrs}{timeconst}" if left_hrs > 0 else "EXPIRED"
        tk.Label(win, text=f"Expiry: {expiry_text} ({status})").pack(pady=(0,8))

        if self.active_user:
            tk.Button(win, text="Buy", width=18, command=lambda: self.open_payment(item, win)).pack(pady=8)
        else:
            tk.Button(win, text="Log in to buy", width=18, command=self.open_login_choice).pack(pady=8)
        tk.Button(win, text="Close", command=win.destroy).pack(pady=6)

    # Payment window
    def open_payment(self, item: FoodItem, parent_win=None):
        pay = tk.Toplevel(self)
        pay.geometry("380x420")
        pay.title("Payment")

        tk.Label(pay, text=f"Pay ${item.price:.2f}", font=("Arial", 12, "bold")).pack(pady=8)
        frm = tk.Frame(pay)
        frm.pack(padx=12, pady=6)

        tk.Label(frm, text="Cardholder").grid(row=0, column=0, sticky='w')
        card_name = make_entry(frm); card_name.grid(row=0, column=1, pady=6)
        tk.Label(frm, text="Card number").grid(row=1, column=0, sticky='w')
        card_num = make_entry(frm); card_num.grid(row=1, column=1, pady=6)
        tk.Label(frm, text="Expiry (MM/YY)").grid(row=2, column=0, sticky='w')
        card_exp = make_entry(frm); card_exp.grid(row=2, column=1, pady=6)
        tk.Label(frm, text="CVV").grid(row=3, column=0, sticky='w')
        card_cvv = make_entry(frm, show="*"); card_cvv.grid(row=3, column=1, pady=6)

        tk.Label(frm, text="Receipt email (optional)").grid(row=4, column=0, sticky='w')
        email_ent = make_entry(frm); email_ent.grid(row=4, column=1, pady=6)

        def confirm():
            # reset visuals
            for w in (card_name, card_num, card_exp, card_cvv, email_ent):
                mark_valid(w)
            if not card_name.get().strip():
                mark_invalid(card_name); messagebox.showwarning("Payment", "Cardholder required"); return
            cn = re.sub(r"\s+", "", card_num.get())
            if not (cn.isdigit() and 12 <= len(cn) <= 19):
                mark_invalid(card_num)
                messagebox.showwarning("Payment", "Card number must be 12-19 digits (spaces allowed).")
                return
            if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", card_exp.get().strip()):
                mark_invalid(card_exp); messagebox.showwarning("Payment", "Expiry must be MM/YY"); return
            mm, yy = card_exp.get().split("/")
            try:
                exp_dt = dt.datetime(2000 + int(yy), int(mm), 1) + dt.timedelta(days=31)
                if exp_dt < dt.datetime.now():
                    mark_invalid(card_exp); messagebox.showwarning("Payment", "Card expired"); return
            except Exception:
                mark_invalid(card_exp); messagebox.showwarning("Payment", "Invalid expiry"); return
            cvv = card_cvv.get().strip()
            if not (cvv.isdigit() and 3 <= len(cvv) <= 4):
                mark_invalid(card_cvv); messagebox.showwarning("Payment", "Invalid CVV"); return
            email = email_ent.get().strip()
            if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                mark_invalid(email_ent); messagebox.showwarning("Payment", "Invalid email"); return

            # simulate payment success
            self.active_user.purchases.append(item)
            biz = next((b for b in businesses if b.id == item.business_id), None)
            if biz:
                biz.cash += item.price
                biz.notifications.append(f"{self.active_user.name} bought {item.name} for ${item.price:.2f} on {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
            try:
                food_items.remove(item)
            except ValueError:
                pass
            save_data()
            masked = cn[:-4].rjust(len(cn)-4, "*") + cn[-4:]
            messagebox.showinfo("Paid", f"Payment accepted • charged {masked}")
            pay.destroy()
            if parent_win:
                try: parent_win.destroy()
                except: pass
            self.switch_tab("home")

        tk.Button(pay, text="Confirm", command=confirm, width=18).pack(pady=8)
        tk.Button(pay, text="Cancel", command=pay.destroy).pack()
        
    def withdraw_business(self):
        if not self.active_business:
            return
        amt = self.active_business.cash
        if amt <= 0:
            messagebox.showinfo("Withdraw", "No funds available")
            return
        messagebox.showinfo("Withdraw", f"Withdrew ${amt:.2f}")
        self.active_business.cash = 0.0
        save_data()
        self.populate_profile()
        
    # Profile tab
    def build_profile_tab(self):
        f = self.frames["profile"]
        # clear previous content
        for widget in f.winfo_children():
            widget.destroy()

        f.config(bg="#ffffff", padx=12, pady=12)

        if self.active_business:
            tk.Label(f, text=f"Balance: ${self.active_business.cash:.2f}", font=('Arial', 12)).pack(pady=(4,10))

            # show listings
            tk.Label(f, text="Your Listings:", font=('Arial', 11, 'bold')).pack()
            has_listing = False
            for item in food_items:
                if item.business_id == self.active_business.id:
                    has_listing = True
                    delta = item.expiry - dt.datetime.now()
                    if delta.total_seconds() <= 0:
                        status = "EXPIRED"
                    else:
                        hours = int(delta.total_seconds() // 3600)
                        minutes = int((delta.total_seconds() % 3600) // 60)
                        seconds = int(delta.total_seconds() % 60)
                        if hours > 0:
                            status = f"{hours}h left"
                        elif minutes > 0:
                            status = f"{minutes}m left"
                        else:
                            status = f"{seconds}s left"
                    tk.Label(f, text=f"{item.name} - ${item.price:.2f} - {status}").pack(pady=1)
            if not has_listing:
                tk.Label(f, text="No listings yet.", fg="#888").pack(pady=(6,2))

            # new listing button
            def open_new_listing():
                new_win = tk.Toplevel(self)
                new_win.title("New Listing")
                new_win.geometry("320x380")

                tk.Label(new_win, text="Food Name").pack(pady=(10,2))
                name = tk.Entry(new_win)
                name.pack()

                tk.Label(new_win, text="Category").pack(pady=(6,2))
                categories = ["Fruit","Vegetable","Meat","Grains","Dairy","Frozen","Snacks","Drinks","Prepared","Other"]
                cat_var = tk.StringVar(value=categories[0])
                tk.OptionMenu(new_win, cat_var, *categories).pack()

                tk.Label(new_win, text="Price ($)").pack(pady=(6,2))
                price = tk.Entry(new_win)
                price.pack()

                tk.Label(new_win, text="Hours until expiry").pack(pady=(6,2))
                hours = tk.Entry(new_win)
                hours.pack()

                def confirm_add():
                    if not all([name.get().strip(), price.get().strip(), hours.get().strip()]):
                        messagebox.showwarning("Missing", "All fields are required.")
                        return
                    try:
                        pr = float(price.get())
                        hrs = int(hours.get())
                    except ValueError:
                        messagebox.showwarning("Invalid", "Price and hours must be numbers.")
                        return
                    item = FoodItem(name.get().strip(), cat_var.get().strip(), pr, self.active_business.id, hours=hrs)
                    self.active_business.listings.append(item)
                    food_items.append(item)
                    save_data()
                    messagebox.showinfo("Added", f"Listed {item.name} for ${item.price:.2f}")
                    new_win.destroy()
                    self.build_profile_tab()  # refresh the tab

                tk.Button(new_win, text="Add Listing", command=confirm_add).pack(pady=12)

            tk.Button(f, text="+ New Listing", command=open_new_listing).pack(pady=(10,12))
            tk.Button(f, text="Withdraw", command=self.withdraw_business).pack(pady=(10,12))
            tk.Button(f, text="Log out", command=self.logout_business).pack(pady=8)

    def populate_profile(self):
        f = self.frames["profile"]
        for w in f.winfo_children():
            w.destroy()

        if self.active_user:
            tk.Label(f, text=f"{self.active_user.name}", font=("Arial", 14, "bold"), bg="#ffffff").pack(anchor='w')
            tk.Label(f, text=f"Username: {self.active_user.username}", bg="#ffffff").pack(anchor='w', pady=(6,0))
            tk.Label(f, text="Purchases:", font=("Arial", 12, "bold"), bg="#ffffff").pack(anchor='w', pady=(12,0))
            lst = tk.Listbox(f)
            lst.pack(fill='both', expand=True, pady=(6,0))
            for p in self.active_user.purchases:
                when = getattr(p, 'expiry', None)
                when_text = when.strftime("%Y-%m-%d %H:%M") if isinstance(when, dt.datetime) else ""
                lst.insert('end', f"{p.name} • ${p.price:.2f} • {p.category} • exp {when_text}")
            tk.Button(f, text="Log out", command=self.logout_user).pack(pady=8)

        elif self.active_business:
            # rebuild the profile tab to include new listing button
            self.build_profile_tab()

        else:
            tk.Label(f, text="Not logged in", font=("Arial", 12), bg="#ffffff").pack(anchor='w')
            tk.Button(f, text="Log in / Sign up", command=self.open_login_choice).pack(pady=12)


    def logout_user(self):
        self.active_user = None
        save_data()
        self.refresh_profile_btn()
        self.populate_profile()

    def logout_business(self):
        self.active_business = None
        save_data()
        self.refresh_profile_btn()
        self.populate_profile()

    # Login / Signup
    def open_login_choice(self):
        win = tk.Toplevel(self)
        win.title("Login / Sign Up")
        win.geometry("360x260")
        tk.Label(win, text="Login as:", font=("Arial", 12, "bold")).pack(pady=6)
        tk.Button(win, text="User Login", width=20, command=lambda: (win.destroy(), self.open_auth('user','login'))).pack(pady=6)
        tk.Button(win, text="User Sign Up", width=20, command=lambda: (win.destroy(), self.open_auth('user','signup'))).pack(pady=6)
        tk.Button(win, text="Business Login", width=20, command=lambda: (win.destroy(), self.open_auth('business','login'))).pack(pady=6)
        tk.Button(win, text="Business Sign Up", width=20, command=lambda: (win.destroy(), self.open_auth('business','signup'))).pack(pady=6)

    def open_auth(self, role, mode):
        win = tk.Toplevel(self)
        win.title(f"{role.title()} {mode.title()}")
        win.geometry("380x300")

        frm = tk.Frame(win)
        frm.pack(padx=12, pady=12)

        tk.Label(frm, text="Username").grid(row=0, column=0, sticky='w')
        uname = make_entry(frm); uname.grid(row=0, column=1, pady=6)
        if mode == "signup":
            tk.Label(frm, text="Display name").grid(row=1, column=0, sticky='w')
            dname = make_entry(frm); dname.grid(row=1, column=1, pady=6)
            # password rules
            tk.Label(frm, text="Password must be 8+ chars, with a capital and number.", fg="gray").grid(row=2, column=0, columnspan=2, sticky='w', pady=(0,2))
            pwd_row = 3
        else:
            pwd_row = 1
        tk.Label(frm, text="Password").grid(row=pwd_row, column=0, sticky='w')
        pwd = make_entry(frm, show="*"); pwd.grid(row=pwd_row, column=1, pady=6)
        if mode == "signup":
            tk.Label(frm, text="Confirm").grid(row=pwd_row+1, column=0, sticky='w')
            cpwd = make_entry(frm, show="*"); cpwd.grid(row=pwd_row+1, column=1, pady=6)

        def do_login():
            u = uname.get().strip(); p = pwd.get().strip()
            mark_valid(uname); mark_valid(pwd)
            if not (u and p):
                mark_invalid(uname); mark_invalid(pwd)
                messagebox.showwarning("Error", "Provide username and password"); return
            if role == "user":
                for usr in users:
                    if usr.username == u and verify_password(usr.password, p):
                        self.active_user = usr
                        self.active_business = None
                        self.refresh_profile_btn()
                        save_data()
                        win.destroy()
                        self.switch_tab("home")
                        return
            else:
                for biz in businesses:
                    if biz.username == u and verify_password(biz.password, p):
                        self.active_business = biz
                        self.active_user = None
                        # show notifications
                        if biz.notifications:
                            msg = "\n".join(biz.notifications)
                            messagebox.showinfo("Notifications", msg)
                            biz.notifications.clear()
                            save_data()
                        self.refresh_profile_btn()
                        win.destroy()
                        self.switch_tab("profile")
                        return
            mark_invalid(uname); mark_invalid(pwd)
            messagebox.showerror("Error", "Invalid credentials")

        def do_signup():
            u = uname.get().strip(); p = pwd.get().strip(); cp = cpwd.get().strip(); dn = dname.get().strip()
            # reset visuals
            for w in (uname, pwd, cpwd, dname):
                mark_valid(w)
            if not (u and p and cp and dn):
                for w in (uname, pwd, cpwd, dname):
                    if not w.get().strip():
                        mark_invalid(w)
                messagebox.showwarning("Error", "All fields required"); return
            if p != cp:
                mark_invalid(pwd); mark_invalid(cpwd)
                messagebox.showwarning("Error", "Passwords do not match"); return
            if len(p) < 8 or not re.search(r'\d', p) or not re.search(r'[A-Z]', p):
                mark_invalid(pwd)
                messagebox.showwarning("Error", "Password must be 8+ chars, with a capital and number"); return
            # username check
            if any(u == x.username for x in users) or any(u == b.username for b in businesses):
                mark_invalid(uname)
                messagebox.showwarning("Error", "Username already taken"); return
            if role == "user":
                new = User(u, p, dn)
                users.append(new)
                self.active_user = new
                self.active_business = None
            else:
                new = Business(u, p, dn)
                businesses.append(new)
                self.active_business = new
                self.active_user = None
            save_data()
            self.refresh_profile_btn()
            messagebox.showinfo("Success", "Account created")
            win.destroy()
            self.switch_tab("home")

        if mode == "login":
            tk.Button(win, text="Login", command=do_login).pack(pady=8)
        else:
            tk.Button(win, text="Sign Up", command=do_signup).pack(pady=8)
        tk.Button(win, text="Cancel", command=win.destroy).pack()
    
    # Quick profile menus
    def open_user_menu(self):
        # small menu for user
        m = tk.Toplevel(self); m.geometry("260x200"); m.title("User")
        tk.Label(m, text=f"{self.active_user.name}", font=("Arial", 12, "bold")).pack(pady=8)
        tk.Button(m, text="View Profile", width=22, command=lambda: (m.destroy(), self.switch_tab("profile"))).pack(pady=6)
        tk.Button(m, text="View Food", width=22, command=lambda: (m.destroy(), self.switch_tab("food"))).pack(pady=6)
        tk.Button(m, text="Logout", width=22, command=lambda: (m.destroy(), self.logout_user())).pack(pady=6)

    def open_business_listings(self):
        win = tk.Toplevel(self)
        win.geometry("360x420")
        win.title("My Listings")
        lb = tk.Listbox(win)
        lb.pack(fill='both', expand=True, padx=8, pady=8)
        now = dt.datetime.now()
        for it in food_items:
            if it.business_id == self.active_business.id:
                timeleft = int((it.expiry - now).total_seconds() / 3600)
                timeconst = "h"
                if timeleft == 0:
                    timeleft = int((it.expiry - now).total_seconds() / 60)
                    timeconst = "m"
                    if timeleft == 0:
                        timeleft = int((it.expiry - now).total_seconds())
                        timeconst = "s"
                status = f"{timeleft}{timeconst} left" if {timeleft} > 0 else "EXPIRED"
                lb.insert('end', f"{it.name} • ${it.price:.2f} • {status}")
        tk.Button(win, text="Close", command=win.destroy).pack(pady=8)
        
    def open_business_menu(self):
        m = tk.Toplevel(self); m.geometry("280x220"); m.title("Business")
        tk.Label(m, text=f"{self.active_business.name}", font=("Arial", 12, "bold")).pack(pady=8)
        tk.Button(m, text="My Listings", width=24, command=lambda: (m.destroy(), self.open_business_listings())).pack(pady=6)
        tk.Button(m, text=f"Withdraw (${self.active_business.cash:.2f})", width=24, command=lambda: (m.destroy(), self.withdraw_business())).pack(pady=6)
        tk.Button(m, text="Logout", width=24, command=lambda: (m.destroy(), self.logout_business())).pack(pady=6)

# ============================================================
# RUN THE APPLICATION
# ============================================================

if __name__ == "__main__":
    app = App()
    app.mainloop()
