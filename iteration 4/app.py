##############################################################
# FOOD SUSTAINABILITY APP
# Description: A tkinter-based app for users and businesses to list, browse, and buy food items to reduce waste.
# Features:
#   - User and business login/signup
#   - Businesses can list food items
#   - Users can browse and buy food
#   - Data saved/loaded from JSON file
# Updates:
#   - Major UI revamp: food boxes, icons, colours, fun facts, money saved, profile stats
#   - Security questions for password recovery
##############################################################

import tkinter as tk
from tkinter import messagebox
import datetime as dt
import json, uuid, re, threading, queue, os, hashlib, binascii, random

# ============================================================
# PASSWORD HASHING & SECURITY QUESTIONS
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

SECURITY_QUESTIONS = [
    "What is your favourite food?",
    "What city were you born in?",
    "What is your pet's name?",
    "What is your favourite colour?",
]

# ============================================================
# CLASSES
# ============================================================

class FoodItem:
    def __init__(self, name, category, price, business_id, expiry=None, id=None, hours=0, weight=0.0, distance="Unknown"):
        self.name = name
        self.category = category
        self.price = float(price)
        self.weight = float(weight)
        self.distance = distance
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
    def __init__(self, username, password, name, id=None, purchases=None, sec_q=None, sec_a=None):
        self.username = username
        self.password = password if isinstance(password, dict) else hash_password(password)
        self.name = name
        self.id = id if id else str(uuid.uuid4())
        self.purchases = purchases if purchases else []
        self.sec_q = sec_q
        self.sec_a = sec_a

    def to_dict(self):
        return {
            "username": self.username,
            "password": self.password,
            "name": self.name,
            "id": self.id,
            "purchases": [p.to_dict() for p in self.purchases],
            "sec_q": self.sec_q,
            "sec_a": self.sec_a,
        }

class Business:
    def __init__(self, username, password, name, id=None, listings=None, cash=0.0, notifications=None, sec_q=None, sec_a=None):
        self.username = username
        self.password = password if isinstance(password, dict) else hash_password(password)
        self.name = name
        self.id = id if id else str(uuid.uuid4())
        self.listings = listings if listings else []
        self.cash = float(cash)
        self.notifications = notifications if notifications else []
        self.sec_q = sec_q
        self.sec_a = sec_a

    def to_dict(self):
        return {
            "username": self.username,
            "password": self.password,
            "name": self.name,
            "id": self.id,
            "listings": [li.to_dict() for li in self.listings],
            "cash": self.cash,
            "notifications": self.notifications,
            "sec_q": self.sec_q,
            "sec_a": self.sec_a,
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
    except Exception:
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
    users.append(User(
        ru.get("username"), pwd, ru.get("name", ru.get("username")),
        id=ru.get("id"), purchases=purchases,
        sec_q=ru.get("sec_q"), sec_a=ru.get("sec_a")
    ))

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
    businesses.append(Business(
        rb.get("username"), pwd, rb.get("name", rb.get("username")),
        id=rb.get("id"), listings=listings, cash=rb.get("cash", 0.0),
        notifications=rb.get("notifications", [])
    ))

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
        self.app_width = 460
        self.app_height = 780
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
        self.topbar = tk.Frame(self, height=64, bg="#eaf6ff")
        self.topbar.pack(fill='x')
        self.topbar.pack_propagate(False)
        self.app_label = tk.Label(self.topbar, text="FoodFlow", font=("Arial", 18, "bold"), bg="#eaf6ff", fg="#2a5d8f")
        self.app_label.pack(side='left', padx=12)
        # profile icon area
        self.profile_btn = tk.Button(self.topbar, text="Log In", relief='flat', bg="#eaf6ff", command=self.handle_profile_click)
        self.profile_btn.pack(side='right', padx=12)

        # main content area
        self.container = tk.Frame(self, bg="#f8fbff")
        self.container.pack(fill='both', expand=True, padx=8, pady=(8,4))

        # bottom nav
        self.bottom = tk.Frame(self, height=64, bg="#eaf6ff")
        self.bottom.pack(fill='x')
        self.bottom.pack_propagate(False)
        self.bottom.columnconfigure((0,1,2), weight=1)
        self.home_btn = tk.Button(self.bottom, text="Home", command=lambda: self.switch_tab("home"), width=14, bg="#eaf6ff", font=("Arial", 11, "bold"))
        self.food_btn = tk.Button(self.bottom, text="Food", command=lambda: self.switch_tab("food"), width=14, bg="#eaf6ff", font=("Arial", 11, "bold"))
        self.profile_tab_btn = tk.Button(self.bottom, text="Profile", command=lambda: self.switch_tab("profile"), width=14, bg="#eaf6ff", font=("Arial", 11, "bold"))
        self.home_btn.grid(row=0, column=0, padx=8, pady=12, sticky='ew')
        self.food_btn.grid(row=0, column=1, padx=8, pady=12, sticky='ew')
        self.profile_tab_btn.grid(row=0, column=2, padx=8, pady=12, sticky='ew')

        # frames for tabs
        self.frames = {}
        for name in ("home", "food", "profile"):
            frame = tk.Frame(self.container, bg="#f8fbff")
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
        for w in f.winfo_children():
            w.destroy()

        # Fun Facts
        fun_facts = [
            "Did you know? 1/3 of all food produced is wasted.",
            "Bananas are berries, but strawberries aren't!",
            "Freezing food can help reduce waste.",
            "Eating local saves energy and money.",
            "Carrots were originally purple.",
            "Potatoes were the first food grown in space.",
            "Honey never spoils.",
            "Apples float because they are 25% air.",
            "Broccoli contains more protein than steak.",
            "Lettuce is a member of the sunflower family."
        ]
        fact = random.choice(fun_facts)
        tk.Label(f, text=f"🌟 Fun Fact: {fact}", font=("Arial", 12, "italic"), bg="#d8f5ff", fg="#1a6fa7", wraplength=400, padx=10, pady=8).pack(fill='x', padx=12, pady=(12,4))

        # Money saved section
        saved = 0.0
        if self.active_user:
            saved = sum([p.price for p in self.active_user.purchases])
        tk.Label(f, text=f"💰 Money saved: ${saved:.2f}", font=("Arial", 13, "bold"), bg="#e3f6fc", fg="#4a7f2c", padx=10, pady=8).pack(fill='x', padx=12, pady=(0,8))

        # Recommended food items (as boxes, scrollable, 2 rows, 1 per row)
        tk.Label(f, text="Recommended", font=("Arial", 14, "bold"), bg="#f8fbff").pack(anchor='w', padx=12, pady=(8,4))
        rec_frame = tk.Frame(f, bg="#f8fbff")
        rec_frame.pack(fill='x', padx=12, pady=(0,6))
        rec_canvas = tk.Canvas(rec_frame, bg="#f8fbff", height=250, highlightthickness=0)
        rec_canvas.pack(side='left', fill='both', expand=True)
        scrollbar = tk.Scrollbar(rec_frame, orient="vertical", command=rec_canvas.yview)
        scrollbar.pack(side='right', fill='y')
        rec_canvas.configure(yscrollcommand=scrollbar.set)
        rec_inner = tk.Frame(rec_canvas, bg="#f8fbff")
        rec_canvas.create_window((0, 0), window=rec_inner, anchor='nw')
        rec_inner.bind("<Configure>", lambda e: rec_canvas.configure(scrollregion=rec_canvas.bbox("all")))

        now = dt.datetime.now()
        recs = sorted([it for it in food_items if it.expiry > now], key=lambda x: (x.expiry, x.price))[:2]
        if not recs:
            tk.Label(rec_inner, text="No recommended items right now", bg="#f8fbff").grid(row=0, column=0, pady=6)
        else:
            for idx, it in enumerate(recs):
                seller = next((b.name for b in businesses if b.id == it.business_id), "Unknown")
                expiry_text = it.expiry.strftime("%Y-%m-%d %H:%M")
                card = tk.Frame(rec_inner, bg="#ffffff", relief='groove', bd=2, padx=12, pady=10)
                icon = tk.Label(card, text="🍏", font=("Arial", 24), bg="#ffffff")
                icon.pack(side='left', padx=(0,12))
                info = tk.Frame(card, bg="#ffffff")
                info.pack(side='left', fill='y')
                tk.Label(info, text=it.name, font=("Arial", 12, "bold"), bg="#ffffff").pack(anchor='w')
                tk.Label(info, text=f"${it.price:.2f} • {it.category} • {seller}", bg="#ffffff", fg="#2a5d8f").pack(anchor='w')
                tk.Label(info, text=f"exp {expiry_text}", fg="gray", bg="#ffffff").pack(anchor='w')
                tk.Label(info, text=f"Weight: {it.weight:.1f}kg", bg="#ffffff", fg="#4a7f2c").pack(anchor='w')
                tk.Label(info, text=f"Distance: {it.distance}", bg="#ffffff", fg="#4a7f2c").pack(anchor='w')
                # Buy button logic
                if self.active_user:
                    buy_btn = tk.Button(card, text="Buy", font=("Arial", 11, "bold"), bg="#d4f7e3", command=lambda item=it: self.show_item_detail(item))
                elif self.active_business:
                    buy_btn = tk.Button(card, text="Log in as user to buy", font=("Arial", 11), bg="#e3f6fc", state='disabled')
                else:
                    buy_btn = tk.Button(card, text="Log in to buy", font=("Arial", 11), bg="#e3f6fc", state='disabled')
                buy_btn.pack(side='right', padx=8)
                # Only 1 card per row
                card.grid(row=idx, column=0, padx=8, pady=8, sticky='nsew')

        # Recent activity
        tk.Label(f, text="Recent activity", font=("Arial", 12, "bold"), bg="#f8fbff").pack(anchor='w', padx=12, pady=(12,0))
        self.activity_box = tk.Listbox(f, height=6, bg="#f7f7f7", fg="#333", font=("Arial", 10))
        self.activity_box.pack(fill='both', padx=12, pady=6, expand=True)

    def populate_home(self):
        self.build_home_tab()
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
        for w in f.winfo_children():
            w.destroy()

        # Search bar
        search_frame = tk.Frame(f, bg="#d8f5ff")
        search_frame.pack(fill='x', padx=12, pady=(12,4))
        tk.Label(search_frame, text="🔍 Search", bg="#d8f5ff", font=("Arial", 12)).pack(side='left', padx=(0,6))
        self.search_var = tk.StringVar()
        self.search_entry = make_entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side='left', fill='x', expand=True, padx=(0,12), pady=6)
        self.search_entry.bind("<Return>", lambda e: self.populate_food())
        self.search_entry.bind("<KeyRelease>", lambda e: self.populate_food())

        # Filter area
        filter_frame = tk.Frame(f, bg="#e3f6fc")
        filter_frame.pack(fill='x', padx=12, pady=(0,4))
        tk.Label(filter_frame, text="Category", bg="#e3f6fc").grid(row=0, column=0, sticky='w')
        self.cat_var = tk.StringVar(value="All")
        self.cat_menu = tk.OptionMenu(filter_frame, self.cat_var, "All")
        self.cat_menu.grid(row=0, column=1, padx=6)
        tk.Button(filter_frame, text="Filter", command=self.populate_food).grid(row=0, column=2, padx=6)

        # Recommended categories (max 2, 2 rows, 1 per row)
        tk.Label(filter_frame, text="Recommended:", bg="#e3f6fc", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky='w', pady=(8,0))
        rec_cats = sorted(set([item.category for item in food_items if item.expiry > dt.datetime.now()]))[:2]
        for idx, cat in enumerate(rec_cats):
            btn = tk.Button(
                filter_frame,
                text=cat,
                font=("Arial", 10),
                relief='ridge',
                bg="#f7f7f7",
                width=14,
                command=lambda v=cat: self.set_category_and_refresh(v)
            )
            btn.grid(row=2+idx, column=0, columnspan=3, padx=4, pady=4, sticky='ew')

        # Food boxes area
        self.food_canvas = tk.Canvas(f, bg="#f8fbff", highlightthickness=0)
        self.food_canvas.pack(fill='both', expand=True, padx=12, pady=(8,8))
        self.food_inner = tk.Frame(self.food_canvas, bg="#f8fbff")
        self.food_canvas.create_window((0, 0), window=self.food_inner, anchor='nw')
        self.food_inner.bind("<Configure>", lambda e: self.food_canvas.configure(scrollregion=self.food_canvas.bbox("all")))

    def populate_food(self):
        # refresh categories
        cats = sorted(set([it.category for it in food_items if it.expiry > dt.datetime.now()]))
        menu = self.cat_menu["menu"]
        menu.delete(0, 'end')
        menu.add_command(label="All", command=lambda v="All": self.cat_var.set(v))
        for c in cats:
            menu.add_command(label=c, command=lambda v=c: self.cat_var.set(v))
        # refresh food boxes
        for w in self.food_inner.winfo_children():
            w.destroy()
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
        # Show as boxes
        if not visible:
            tk.Label(self.food_inner, text="No items match filters", bg="#f8fbff", font=("Arial", 12)).pack(pady=12)
        else:
            for idx, it in enumerate(visible):
                seller = next((b.name for b in businesses if b.id == it.business_id), "Unknown")
                expiry_text = it.expiry.strftime("%Y-%m-%d %H:%M")
                card = tk.Frame(self.food_inner, bg="#ffffff", relief='groove', bd=2, padx=12, pady=10)
                # Icon placeholder
                category_icons = {
                    "Fruit": "🍏",
                    "Vegetable": "🥕",
                    "Meat": "🍖",
                    "Grains": "🌾",
                    "Dairy": "🥛",
                    "Frozen": "🧊",
                    "Snacks": "🍪",
                    "Drinks": "🥤",
                    "Prepared": "🍱",
                    "Other": "🍽️"
                }
                icon_text = category_icons.get(it.category, "🍽️")
                icon = tk.Label(card, text=icon_text, font=("Arial", 24), bg="#ffffff")
                icon.pack(side='left', padx=(0,12))
                info = tk.Frame(card, bg="#ffffff")
                info.pack(side='left', fill='y')
                tk.Label(info, text=it.name, font=("Arial", 12, "bold"), bg="#ffffff").pack(anchor='w')
                tk.Label(info, text=f"${it.price:.2f} • {it.category} • {seller}", bg="#ffffff", fg="#2a5d8f").pack(anchor='w')
                tk.Label(info, text=f"exp {expiry_text}", fg="gray", bg="#ffffff").pack(anchor='w')
                tk.Label(info, text=f"Weight: {it.weight:.1f}kg", bg="#ffffff", fg="#4a7f2c").pack(anchor='w')
                tk.Label(info, text=f"Distance: {it.distance}", bg="#ffffff", fg="#4a7f2c").pack(anchor='w')
                # Buy button logic
                if self.active_user:
                    buy_btn = tk.Button(card, text="Buy", font=("Arial", 11, "bold"), bg="#d4f7e3", command=lambda item=it: self.show_item_detail(item))
                elif self.active_business:
                    buy_btn = tk.Button(card, text="Log in as user to buy", font=("Arial", 11), bg="#e3f6fc", state='disabled')
                else:
                    buy_btn = tk.Button(card, text="Log in to buy", font=("Arial", 11), bg="#e3f6fc", state='disabled')
                buy_btn.pack(side='right', padx=8)
                card.pack(fill='x', padx=8, pady=8)
        self.food_canvas.config(height=min(600, 120*max(1, len(visible))))

    def set_category_and_refresh(self, cat):
        self.cat_var.set(cat)
        self.populate_food()

    # ============================================================
    # PROFILE TAB
    # ============================================================

    def build_profile_tab(self):
        f = self.frames["profile"]
        # clear previous content
        for widget in f.winfo_children():
            widget.destroy()

        f.config(bg="#f8fbff", padx=12, pady=12)

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

                tk.Label(new_win, text="Weight (kg)").pack(pady=(6,2))
                weight = tk.Entry(new_win)
                weight.pack()

                def confirm_add():
                    if not all([name.get().strip(), price.get().strip(), hours.get().strip(), weight.get().strip()]):
                        messagebox.showwarning("Missing", "All fields are required.")
                        return
                    try:
                        pr = float(price.get())
                        hrs = float(hours.get())
                        wt = float(weight.get())
                    except ValueError:
                        messagebox.showwarning("Invalid", "Price, hours, and weight must be numbers.")
                        return
                    item = FoodItem(name.get().strip(), cat_var.get().strip(), pr, self.active_business.id, hours=hrs, weight=wt)
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
            tk.Label(f, text=f"{self.active_user.name}", font=("Arial", 14, "bold"), bg="#f8fbff").pack(anchor='w')
            tk.Label(f, text=f"Username: {self.active_user.username}", bg="#f8fbff").pack(anchor='w', pady=(6,0))
            tk.Label(f, text="Purchases:", font=("Arial", 12, "bold"), bg="#f8fbff").pack(anchor='w', pady=(12,0))
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
            tk.Label(f, text="Not logged in", font=("Arial", 12), bg="#f8fbff").pack(anchor='w')
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
        win.geometry("360x220")
        tk.Label(win, text="Choose:", font=("Arial", 12, "bold")).pack(pady=6)
        # Only one login button, but two sign up buttons
        tk.Button(win, text="Login", width=20, command=lambda: (win.destroy(), self.open_auth('any','login'))).pack(pady=10)
        tk.Button(win, text="Sign Up as User", width=20, command=lambda: (win.destroy(), self.open_auth('user','signup'))).pack(pady=6)
        tk.Button(win, text="Sign Up as Business", width=20, command=lambda: (win.destroy(), self.open_auth('business','signup'))).pack(pady=6)

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
            tk.Label(frm, text="Password must be 8+ chars, with a capital and number.", fg="gray").grid(row=2, column=0, columnspan=2, sticky='w', pady=(0,2))
            pwd_row = 3
        else:
            pwd_row = 1
        tk.Label(frm, text="Password").grid(row=pwd_row, column=0, sticky='w')
        pwd = make_entry(frm, show="*"); pwd.grid(row=pwd_row, column=1, pady=6)
        if mode == "signup":
            tk.Label(frm, text="Confirm").grid(row=pwd_row+1, column=0, sticky='w')
            cpwd = make_entry(frm, show="*"); cpwd.grid(row=pwd_row+1, column=1, pady=6)
            # --- Always show security question for signup ---
            tk.Label(frm, text="Security Question").grid(row=pwd_row+2, column=0, sticky='w')
            secq_var = tk.StringVar(value=SECURITY_QUESTIONS[0])
            tk.OptionMenu(frm, secq_var, *SECURITY_QUESTIONS).grid(row=pwd_row+2, column=1, pady=6)
            tk.Label(frm, text="Answer").grid(row=pwd_row+3, column=0, sticky='w')
            seca = make_entry(frm); seca.grid(row=pwd_row+3, column=1, pady=6)

        def do_login():
            u = uname.get().strip(); p = pwd.get().strip()
            mark_valid(uname); mark_valid(pwd)
            if not (u and p):
                mark_invalid(uname); mark_invalid(pwd)
                messagebox.showwarning("Error", "Provide username and password"); return
            # Try user first
            for usr in users:
                if usr.username == u and verify_password(usr.password, p):
                    self.active_user = usr
                    self.active_business = None
                    self.refresh_profile_btn()
                    save_data()
                    win.destroy()
                    self.switch_tab("home")
                    return
            # Try business
            for biz in businesses:
                if biz.username == u and verify_password(biz.password, p):
                    self.active_business = biz
                    self.active_user = None
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
            for w in (uname, pwd, cpwd, dname, seca):
                mark_valid(w)
            if not (u and p and cp and dn and seca.get().strip()):
                for w in (uname, pwd, cpwd, dname, seca):
                    if not w.get().strip():
                        mark_invalid(w)
                messagebox.showwarning("Error", "All fields required, including security question and answer."); return
            if p != cp:
                mark_invalid(pwd); mark_invalid(cpwd)
                messagebox.showwarning("Error", "Passwords do not match"); return
            if len(p) < 8 or not re.search(r'\d', p) or not re.search(r'[A-Z]', p):
                mark_invalid(pwd)
                messagebox.showwarning("Error", "Password must be 8+ chars, with a capital and number"); return
            if any(u == x.username for x in users) or any(u == b.username for b in businesses):
                mark_invalid(uname)
                messagebox.showwarning("Error", "Username already taken"); return
            secq = secq_var.get()
            seca_val = seca.get().strip()
            if role == "user":
                new = User(u, p, dn, sec_q=secq, sec_a=seca_val)
                users.append(new)
                self.active_user = new
                self.active_business = None
            else:
                new = Business(u, p, dn, sec_q=secq, sec_a=seca_val)
                businesses.append(new)
                self.active_business = new
                self.active_user = None
            save_data()
            self.refresh_profile_btn()
            messagebox.showinfo("Success", "Account created. Security question added and will be used for password recovery.")
            win.destroy()
            self.switch_tab("home")

        if mode == "login":
            tk.Button(win, text="Login", command=do_login).pack(pady=8)
        else:
            tk.Button(win, text="Sign Up", command=do_signup).pack(pady=8)
        tk.Button(win, text="Cancel", command=win.destroy).pack()
        if mode == "login":
            def forgot_password():
                fp_win = tk.Toplevel(win)
                fp_win.title("Forgot Password")
                fp_win.geometry("340x220")
                fp_frame = tk.Frame(fp_win)
                fp_frame.pack(fill='both', expand=True, padx=12, pady=12)

                tk.Label(fp_frame, text="Enter your username:").pack(pady=6)
                fp_uname = make_entry(fp_frame)
                fp_uname.pack(pady=4)

                def next_step():
                    uname = fp_uname.get().strip()
                    # Check both users and businesses
                    account = next((u for u in users if u.username == uname), None)
                    if not account:
                        account = next((b for b in businesses if b.username == uname), None)
                    for w in fp_frame.winfo_children():
                        w.destroy()
                    if not account or not account.sec_q:
                        tk.Label(fp_frame, text="Account not found or no security question set.", fg="red").pack(pady=8)
                        tk.Button(fp_frame, text="Close", command=fp_win.destroy).pack(pady=8)
                        return
                    tk.Label(fp_frame, text=account.sec_q).pack(pady=6)
                    fp_ans = make_entry(fp_frame)
                    fp_ans.pack(pady=4)
                    def check_answer():
                        if fp_ans.get().strip().lower() == (account.sec_a or "").lower():
                            for w in fp_frame.winfo_children():
                                w.destroy()
                            tk.Label(fp_frame, text="Enter new password:").pack(pady=6)
                            new_pwd = make_entry(fp_frame, show="*")
                            new_pwd.pack(pady=4)
                            tk.Label(fp_frame, text="Confirm new password:").pack(pady=6)
                            conf_pwd = make_entry(fp_frame, show="*")
                            conf_pwd.pack(pady=4)
                            def set_new_pwd():
                                np = new_pwd.get().strip()
                                cp = conf_pwd.get().strip()
                                if np != cp:
                                    messagebox.showerror("Error", "Passwords do not match.")
                                    return
                                if len(np) < 8 or not re.search(r'\d', np) or not re.search(r'[A-Z]', np):
                                    messagebox.showerror("Error", "Password must be 8+ chars, with a capital and number.")
                                    return
                                account.password = hash_password(np)
                                save_data()
                                messagebox.showinfo("Success", "Password reset!")
                                fp_win.destroy()
                            tk.Button(fp_frame, text="Set Password", command=set_new_pwd).pack(pady=8)
                        else:
                            messagebox.showerror("Error", "Incorrect answer.")
                    tk.Button(fp_frame, text="Check Answer", command=check_answer).pack(pady=8)
                tk.Button(fp_frame, text="Next", command=next_step).pack(pady=8)
            tk.Button(win, text="Forgot Password?", command=forgot_password).pack(pady=6)

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

    def withdraw_business(self):
        if self.active_business:
            amount = self.active_business.cash
            self.active_business.cash = 0.0
            save_data()
            messagebox.showinfo("Withdraw", f"Withdrawn ${amount:.2f}")
            self.build_profile_tab()

    def show_item_detail(self, item):
        win = tk.Toplevel(self)
        win.title(f"{item.name} Details")
        win.geometry("340x360")
        tk.Label(win, text=item.name, font=("Arial", 14, "bold")).pack(pady=8)
        tk.Label(win, text=f"Category: {item.category}").pack(pady=4)
        tk.Label(win, text=f"Price: ${item.price:.2f}").pack(pady=4)
        tk.Label(win, text=f"Weight: {item.weight:.2f} kg").pack(pady=4)
        tk.Label(win, text=f"Distance: {item.distance}").pack(pady=4)
        tk.Label(win, text=f"Expires: {item.expiry.strftime('%Y-%m-%d %H:%M')}").pack(pady=4)
        seller = next((b.name for b in businesses if b.id == item.business_id), "Unknown")
        tk.Label(win, text=f"Seller: {seller}").pack(pady=4)

        def open_payment():
            pay = tk.Toplevel(win)
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
                try: win.destroy()
                except: pass
                self.switch_tab("home")

            tk.Button(pay, text="Confirm", command=confirm, width=18).pack(pady=8)
            tk.Button(pay, text="Cancel", command=pay.destroy).pack()

        if self.active_user:
            tk.Button(win, text="Buy", font=("Arial", 12, "bold"), bg="#d4f7e3", command=open_payment).pack(pady=10)
        elif self.active_business:
            tk.Button(win, text="Log in as user to buy", state='disabled').pack(pady=10)
        else:
            tk.Button(win, text="Log in to buy", state='disabled').pack(pady=10)

        tk.Button(win, text="Close", command=win.destroy).pack(pady=8)

# ============================================================
# RUN THE APPLICATION
# ============================================================

if __name__ == "__main__":
    app = App()
    app.mainloop()
