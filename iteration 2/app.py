##############################################################
# FOOD SUSTAINABILITY APP
# Description: A tkinter-based app for users and businesses to list, browse, and buy food items to reduce waste.
# Features:
#   - User and business login/signup
#   - Businesses can list food items
#   - Users can browse and buy food
#   - Data saved/loaded from JSON file
# Updates:
#   - Improved category filtering and expiry handling
#   - Added payment flow for purchases
#   - Added password rules and confirmation for signup
#   - Added business withdrawal and listings
##############################################################

import tkinter as tk
from tkinter import messagebox
import datetime as dt
import json, uuid, re, threading, queue, os

# ============================================================
# CLASSES
# ============================================================

class User:
    def __init__(self, username, password, name, id=None, purchases=None):
        self.username = username
        self.password = password
        self.name = name
        self.id = id if id else str(uuid.uuid4())
        self.purchases = purchases if purchases else []

class Business:
    def __init__(self, username, password, name, id=None, listings=None, cash=0.0):
        self.username = username
        self.password = password
        self.name = name
        self.id = id if id else str(uuid.uuid4())
        self.listings = listings if listings else []
        self.cash = cash

class FoodItem:
    def __init__(self, name, category, price, business_id, expiry=None, id=None, hours=0):
        self.name = name
        self.category = category
        self.price = price
        self.business_id = business_id
        self.expiry = expiry if expiry else dt.datetime.now() + dt.timedelta(hours=hours)
        self.id = id if id else str(uuid.uuid4())

# ============================================================
# SAVE AND LOAD
# ============================================================

# Always use the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

def load_data():
    """
    Loads data from the JSON file.
    Returns a dictionary with users, businesses, and food_items lists.
    Handles blank files and missing files gracefully.
    """
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {"users": [], "businesses": [], "food_items": []}
            return json.loads(content)
    except FileNotFoundError:
        return {"users": [], "businesses": [], "food_items": []}

def load_data_thread(data):
    """
    Loads data in a separate thread and puts the result in a queue.
    Used for non-blocking startup.
    """
    result = load_data()
    data.put(result)

def save_data():
    """
    Saves the current users, businesses, and food_items to the JSON file.
    Uses default=str to handle datetime serialization.
    """
    with open(DATA_FILE, "w") as f:
        json.dump({
            "users": [user.__dict__ for user in users],
            "businesses": [biz.__dict__ for biz in businesses],
            "food_items": [food.__dict__ for food in food_items],
        }, f, indent=4, default=str)

# ============================================================
# GLOBALS
# ============================================================

users, businesses, food_items = [], [], []
data_queue = queue.Queue()
load_thread = threading.Thread(target=load_data_thread, args=(data_queue,))
load_thread.start()
load_thread.join(timeout=1)

if not data_queue.empty():
    data = data_queue.get()
else:
    data = {"users": [], "businesses": [], "food_items": []}

for u in data['users']:
    users.append(User(**u))
for b in data['businesses']:
    biz = Business(**b)
    biz.cash = b.get('cash', 0.0)
    businesses.append(biz)
for f in data['food_items']:
    # Ensure expiry is datetime
    try:
        f["expiry"] = dt.datetime.fromisoformat(f["expiry"]) if isinstance(f.get("expiry"), str) else f.get("expiry")
    except Exception:
        f["expiry"] = dt.datetime.now()
    food_items.append(FoodItem(**f))

# ============================================================
# GUI
# ============================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FoodFlow")
        self.geometry("700x500")
        self.active_user, self.active_business = None, None
        self.show_main_menu()

    # --------------------------------------------------------
    # CLEAR ALL WIDGETS
    # --------------------------------------------------------
    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------
    def show_main_menu(self):
        self.clear()
        tk.Label(self, text="Welcome to Food Sustainability App", font=("Arial", 18)).pack(pady=20)
        tk.Button(self, text="Login", width=20, command=self.login_choice).pack(pady=5)
        tk.Button(self, text="Sign Up", width=20, command=self.signup_choice).pack(pady=5)

    # --------------------------------------------------------
    # LOGIN CHOICE
    # --------------------------------------------------------
    def login_choice(self):
        self.clear()
        tk.Label(self, text="Login as:", font=("Arial", 14)).pack(pady=10)
        tk.Button(self, text="User", width=15, command=lambda: self.log_sign('user','login')).pack(pady=5)
        tk.Button(self, text="Business", width=15, command=lambda: self.log_sign('business','login')).pack(pady=5)
        tk.Button(self, text="Back", command=self.show_main_menu).pack(pady=10)

    # --------------------------------------------------------
    # SIGNUP CHOICE
    # --------------------------------------------------------
    def signup_choice(self):
        self.clear()
        tk.Label(self, text="Sign Up as:", font=("Arial", 14)).pack(pady=10)
        tk.Button(self, text="User", width=15, command=lambda: self.log_sign('user','signup')).pack(pady=5)
        tk.Button(self, text="Business", width=15, command=lambda: self.log_sign('business','signup')).pack(pady=5)
        tk.Button(self, text="Back", command=self.show_main_menu).pack(pady=10)

    # --------------------------------------------------------
    # LOGIN/SIGNUP SCREEN
    # --------------------------------------------------------
    def log_sign(self, role, mode):
        self.clear()

        tk.Label(self, text=f"{role.title()} {mode.title()}", font=("Arial", 14, "bold")).pack(pady=10)

        tk.Label(self, text="Username").pack()
        username = tk.Entry(self)
        username.pack()

        # Display name (signup only)
        name_label = tk.Label(self, text="Display Name")
        name_entry = tk.Entry(self)

        # Password
        tk.Label(self, text="Password").pack()
        password = tk.Entry(self, show="*")
        password.pack()

        # Confirm password (signup only)
        conf_label = tk.Label(self, text="Confirm Password")
        conf_entry = tk.Entry(self, show="*")

        # Password rules shown in advance
        pwd_rules = tk.Label(self, text="Password must be at least 8 characters, include a capital letter and a number.")

        def do_login():
            """
            Handles login for user or business.
            Checks credentials and sets active user/business.
            """
            u, p = username.get().strip(), password.get().strip()
            if role == "user":
                for user in users:
                    if user.username == u and user.password == p:
                        self.active_user = user
                        self.show_user_menu()
                        return
            else:
                for biz in businesses:
                    if biz.username == u and biz.password == p:
                        self.active_business = biz
                        self.show_business_menu()
                        return
            messagebox.showerror("Error", "Invalid login.")

        def do_signup():
            """
            Handles signup for user or business.
            Checks all fields, password confirmation, and password rules.
            Adds new user/business and saves data.
            """
            u, p, n, cp = username.get().strip(), password.get().strip(), name_entry.get().strip(), conf_entry.get().strip()
            if not (u and p and n and cp):
                messagebox.showwarning("Error", "All fields required.")
                return
            if p != cp:
                messagebox.showwarning("Error", "Passwords do not match.")
                return

            # checks
            if len(p) < 8 or not re.search(r'\d', p) or not re.search(r'[A-Z]', p):
                messagebox.showwarning("Error", "Password must be at least 8 characters, and include a capital letter and number.")
                return

            if role == "user":
                new = User(u, p, n)
                users.append(new)
                self.active_user = new
                self.show_user_menu()
            else:
                new = Business(u, p, n)
                businesses.append(new)
                self.active_business = new
                self.show_business_menu()
            save_data()

        # Place widgets depending on mode
        if mode == 'signup':
            name_label.pack()
            name_entry.pack()
            pwd_rules.pack(pady=5)
            conf_label.pack()
            conf_entry.pack()
            tk.Button(self, text="Sign Up", command=do_signup).pack(pady=10)
        else:
            tk.Button(self, text="Login", command=do_login).pack(pady=10)

        tk.Button(self, text="Back", command=self.show_main_menu).pack(pady=5)

    # --------------------------------------------------------
    # USER MENU
    # --------------------------------------------------------
    def show_user_menu(self):
        self.clear()
        tk.Label(self, text=f"Welcome, {self.active_user.name}", font=("Arial", 14)).pack(pady=10)
        tk.Button(self, text="Browse Food", width=20, command=self.browse_food).pack(pady=5)
        tk.Button(self, text="Buy Food", width=20, command=self.buy_food_menu).pack(pady=5)
        tk.Button(self, text="Back", width=20, command=self.show_main_menu).pack(pady=5)

    # --------------------------------------------------------
    # BROWSE FOOD
    # --------------------------------------------------------
    def browse_food(self):
        """
        Shows available food items in a listbox.
        Allows filtering by category.
        """
        self.clear()
        tk.Label(self, text="Available Food", font=("Arial", 14)).pack(pady=10)

        # Category filter dropdown
        categories = sorted(set([item.category for item in food_items if item.expiry > dt.datetime.now()]))
        category_var = tk.StringVar(value="All")
        cat_menu = tk.OptionMenu(self, category_var, "All", *categories)
        cat_menu.pack(pady=5)

        list_frame = tk.Frame(self)
        list_frame.pack(fill='both', expand=True)

        listbox = tk.Listbox(list_frame, width=80)
        listbox.pack(side='left', fill='both', expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient='vertical')
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side='right', fill='y')
        listbox.config(yscrollcommand=scrollbar.set)

        def refresh_list(*_):
            """
            Refreshes the food list based on selected category.
            """
            selected_cat = category_var.get()
            listbox.delete(0, 'end')
            for item in food_items:
                if item.expiry > dt.datetime.now():
                    if selected_cat == "All" or item.category == selected_cat:
                        listbox.insert('end', f"{item.name} - ${item.price:.2f} - {item.category}")

        category_var.trace('w', refresh_list)
        refresh_list()

        tk.Button(self, text="Back", command=self.show_user_menu).pack(pady=10)

    # --------------------------------------------------------
    # BUY FOOD
    # --------------------------------------------------------
    def buy_food_menu(self):
        """
        Shows a list of food items to buy.
        Opens a payment window for the selected item.
        """
        self.clear()
        tk.Label(self, text="Select an item to buy", font=("Arial", 14)).pack(pady=10)

        listbox = tk.Listbox(self, width=80)
        listbox.pack(padx=10, pady=5)

        valid_items = [item for item in food_items if item.expiry > dt.datetime.now()]
        for item in valid_items:
            listbox.insert('end', f"{item.name} - ${item.price:.2f} - {item.category}")

        def open_payment():
            """
            Opens a payment window for the selected food item.
            Handles fake payment details and updates purchases.
            """
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Choose item", "Please select an item to buy.")
                return
            idx = sel[0]
            item = valid_items[idx]
            # Fake payment flow
            pay_win = tk.Toplevel(self)
            pay_win.title("Payment")
            tk.Label(pay_win, text=f"Buying: {item.name} - ${item.price:.2f}", font=("Arial", 12)).pack(pady=10)

            tk.Label(pay_win, text="Cardholder Name").pack()
            card_name = tk.Entry(pay_win)
            card_name.pack()
            tk.Label(pay_win, text="Card Number (fake)").pack()
            card_num = tk.Entry(pay_win)
            card_num.pack()
            tk.Label(pay_win, text="Expiry MM/YY").pack()
            card_exp = tk.Entry(pay_win)
            card_exp.pack()
            tk.Label(pay_win, text="CVV").pack()
            card_cvv = tk.Entry(pay_win)
            card_cvv.pack()

            def confirm_payment():
                """
                Confirms payment and completes purchase.
                Checks for valid input and updates user/business data.
                """
                if not card_name.get().strip() or not card_num.get().strip() or not card_exp.get().strip() or not card_cvv.get().strip():
                    messagebox.showwarning("Payment", "Please fill payment details (fake).")
                    return
                try: 
                    card_number, card_expiry, card_cvvnum = int(card_num.get()), int(card_exp.get()), int(card_cvv.get())
                except:
                    messagebox.showwarning("Payment", "Invalid input.")
                    return
                # complete purchase
                self.active_user.purchases.append(item)
                for biz in businesses:
                    if biz.id == item.business_id:
                        biz.cash += item.price
                try:
                    food_items.remove(item)
                except ValueError:
                    pass
                save_data()
                messagebox.showinfo("Success", f"Payment confirmed. Bought {item.name} for ${item.price:.2f}")
                pay_win.destroy()
                self.show_user_menu()

            tk.Button(pay_win, text="Confirm Payment", command=confirm_payment).pack(pady=10)
            tk.Button(pay_win, text="Cancel", command=pay_win.destroy).pack(pady=5)

        tk.Button(self, text="Buy", command=open_payment).pack(pady=5)
        tk.Button(self, text="Back", command=self.show_user_menu).pack(pady=5)

    # --------------------------------------------------------
    # BUSINESS MENU
    # --------------------------------------------------------
    def show_business_menu(self):
        self.clear()
        tk.Label(self, text=f"Business: {self.active_business.name}", font=("Arial", 14)).pack(pady=10)
        tk.Button(self, text="List Food", width=20, command=self.list_food).pack(pady=5)
        tk.Button(self, text="My Listings", width=20, command=self.view_listings).pack(pady=5)
        tk.Button(self, text=f"Withdraw (${self.active_business.cash:.2f})", width=20, command=self.withdraw).pack(pady=5)
        tk.Button(self, text="Back", width=20, command=self.show_main_menu).pack(pady=5)

    # --------------------------------------------------------
    # LIST FOOD
    # --------------------------------------------------------
    def list_food(self):
        """
        Allows businesses to list a new food item.
        Checks for valid input and adds item to listings.
        """
        self.clear()
        tk.Label(self, text="Food Name").pack()
        name = tk.Entry(self)
        name.pack()

        tk.Label(self, text="Category").pack()
        # Category dropdown (predefined categories + allow custom)
        categories = ["Fruit", "Vegetable", "Meat", "Grains", "Dairy", "Frozen", "Snacks", "Drinks", "Prepared", "Other"]
        cat_var = tk.StringVar(value=categories[0])
        cat_menu = tk.OptionMenu(self, cat_var, *categories)
        cat_menu.pack()
        tk.Label(self, text="Price").pack()
        price = tk.Entry(self)
        price.pack()
        tk.Label(self, text="Hours till expiry").pack()
        hours = tk.Entry(self)
        hours.pack()

        def add():
            """
            Adds a new food item to the business listings and global food list.
            Checks for valid input and saves data.
            """
            if name.get() == "" or price.get() == "" or hours.get() == "":
                messagebox.showwarning("Error", "All fields required.")
                return
            try:
                pr = float(price.get())
                hrs = int(hours.get())
            except Exception:
                messagebox.showwarning("Error", "Invalid input.")
                return
            item = FoodItem(name.get().strip(), cat_var.get().strip(), pr, self.active_business.id, hours=hrs)
            self.active_business.listings.append(item)
            food_items.append(item)
            save_data()
            messagebox.showinfo("Success", f"Listed {item.name}")
            self.show_business_menu()

        tk.Button(self, text="Add Food", command=add).pack(pady=5)
        tk.Button(self, text="Back", command=self.show_business_menu).pack(pady=5)

    # --------------------------------------------------------
    # VIEW LISTINGS
    # --------------------------------------------------------
    def view_listings(self):
        """
        Shows the business's current food listings.
        Displays expiry status for each item.
        """
        self.clear()
        tk.Label(self, text="Your Listings", font=("Arial", 14)).pack(pady=10)
        for item in food_items:
            if item.business_id == self.active_business.id:
                expiry = (item.expiry - dt.datetime.now()).total_seconds() / 3600
                status = f"Expires in {int(expiry)}h" if expiry > 0 else "EXPIRED"
                tk.Label(self, text=f"{item.name} - ${item.price:.2f} - {status}").pack()
        tk.Button(self, text="Back", command=self.show_business_menu).pack(pady=5)

    # --------------------------------------------------------
    # WITHDRAW
    # --------------------------------------------------------
    def withdraw(self):
        """
        Allows businesses to withdraw their earnings.
        Resets cash to zero and saves data.
        """
        messagebox.showinfo("Withdraw", f"Withdrawn ${self.active_business.cash:.2f}")
        self.active_business.cash = 0.0
        save_data()
        self.show_business_menu()

# ============================================================
# RUN THE APPLICATION
# ============================================================

if __name__ == '__main__':
    app = App()
    app.mainloop()
