import tkinter as tk
from tkinter import messagebox
import datetime as dt
import json, uuid, re, time, threading, queue

# Classes
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

# Save and load
data_queue = queue.Queue()

def load_data():
    try:
        with open("data.json", "r") as f:
            content = f.read().strip()
            if not content:
                return {"users": [], "businesses": [], "food_items": []}
            return json.loads(content)
    except FileNotFoundError:
        return {"users": [], "businesses": [], "food_items": []}

def save_data():
    with open("data.json", "w") as f:
        json.dump({
            "users": [user.__dict__ for user in users],
            "businesses": [biz.__dict__ for biz in businesses],
            "food_items": [food.__dict__ for food in food_items],
        }, f, indent=4, default=str)

# Global
users, businesses, food_items = [], [], []
data = load_data()

for u in data['users']:
    users.append(User(**u))
for b in data['businesses']:
    biz = Business(**b)
    biz.cash = b.get('cash', 0.0)
    businesses.append(biz)
for f in data['food_items']:
    f["expiry"] = dt.datetime.fromisoformat(f["expiry"])
    food_items.append(FoodItem(**f))

# GUI
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Food Sustainability App")
        self.geometry("600x400")
        self.active_user, self.active_business = None, None
        self.show_main_menu()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def show_main_menu(self):
        self.clear()
        tk.Label(self, text="Welcome to Food Sustainability App", font=("Arial", 18)).pack(pady=20)
        tk.Button(self, text="User Login", command=lambda: self.log_sign("user")).pack(pady=5)
        tk.Button(self, text="Business Login", command=lambda: self.log_sign("business")).pack(pady=5)

    def log_sign(self, role):
        space = "                       "
        self.clear()
        mode = tk.StringVar(value="login")  # Default as login

        top_frame = tk.Frame(self)
        top_frame.pack(fill='x', pady=10)

        # Title label centered
        title_label = tk.Label(top_frame, text=f"{space}{role.title()} Login", font=("Arial", 14, "bold"), anchor='center')
        title_label.grid(row=0, column=0, sticky="ew")

        # Switch mode button right
        toggle_btn = tk.Button(top_frame, text="Sign Up Instead", command=lambda: switch_mode())
        toggle_btn.grid(row=0, column=1, sticky="e", padx=10)

        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_columnconfigure(1, weight=0)

        # Username
        tk.Label(self, text="Username").pack()
        username = tk.Entry(self)
        username.pack()

        # Display name (signup only)
        name_label = tk.Label(self, text="Display Name")
        name_entry = tk.Entry(self)

        # Password
        password_label = tk.Label(self, text="Password")
        password_label.pack()
        password = tk.Entry(self, show="*")
        password.pack()

        def switch_mode():
            if mode.get() == "login":
                mode.set("signup")
                title_label.config(text=f"{space}{role.title()} Sign Up")
                toggle_btn.config(text="Login Instead")
                name_entry.pack(before=password_label)
                name_label.pack(before=name_entry)
                submit_btn.config(text="Sign Up", command=signup)
            else:
                mode.set("login")
                title_label.config(text=f"{space}{role.title()} Login")
                toggle_btn.config(text="Sign Up Instead")
                name_label.pack_forget()
                name_entry.pack_forget()
                submit_btn.config(text="Login", command=login)

        def login():
            u, p = username.get(), password.get()
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

        def signup():
            u, p, n = username.get(), password.get(), name_entry.get()
            if not (u and p and n):
                messagebox.showwarning("Error", "All fields required.")
                return
            
            # Recursive password check
            def recursive_password_check(password, conditions):
                if not conditions:
                    return True
                check = conditions[0]
                return check(password) and recursive_password_check(password, conditions[1:])
            
            checks = [lambda p: len(p) >= 8, lambda p: re.search(r'\d', p), lambda p: re.search(r'[A-Z]', p)]

            if not recursive_password_check(p, checks):
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

        submit_btn = tk.Button(self, text="Login", command=login)
        submit_btn.pack(pady=5)

        tk.Button(self, text="Back", command=self.show_main_menu).pack(pady=5)


    def show_user_menu(self):
        self.clear()
        tk.Label(self, text=f"Welcome, {self.active_user.name}", font=("Arial", 14)).pack(pady=10)
        tk.Button(self, text="Browse Food", command=self.browse_food).pack(pady=5)
        tk.Button(self, text="Buy Food", command=self.buy_food).pack(pady=5)
        tk.Button(self, text="Back", command=self.show_main_menu).pack(pady=5)

    def browse_food(self):
        self.clear()
        tk.Label(self, text="Available Food", font=("Arial", 14)).pack(pady=10)
        for item in food_items:
            if item.expiry > dt.datetime.now():
                text = f"{item.name} - ${item.price} - {item.category}"
                tk.Label(self, text=text).pack()
        tk.Button(self, text="Back", command=self.show_user_menu).pack(pady=10)

    def buy_food(self):
        self.clear()
        tk.Label(self, text="Enter food name to buy:").pack()
        entry = tk.Entry(self)
        entry.pack()

        def buy():
            name = entry.get().lower()
            for item in food_items:
                if item.name.lower() == name and item.expiry > dt.datetime.now():
                    self.active_user.purchases.append(item)
                    for biz in businesses:
                        if biz.id == item.business_id:
                            biz.cash += item.price
                    food_items.remove(item)
                    save_data()
                    messagebox.showinfo("Success", f"Bought {item.name} for ${item.price}")
                    return
            messagebox.showerror("Error", "Item not found or expired")

        tk.Button(self, text="Buy", command=buy).pack(pady=5)
        tk.Button(self, text="Back", command=self.show_user_menu).pack(pady=5)

    def show_business_menu(self):
        self.clear()
        tk.Label(self, text=f"Business: {self.active_business.name}", font=("Arial", 14)).pack(pady=10)
        tk.Button(self, text="List Food", command=self.list_food).pack(pady=5)
        tk.Button(self, text="My Listings", command=self.view_listings).pack(pady=5)
        tk.Button(self, text=f"Withdraw (${self.active_business.cash})", command=self.withdraw).pack(pady=5)
        tk.Button(self, text="Back", command=self.show_main_menu).pack(pady=5)

    def list_food(self):
        self.clear()
        tk.Label(self, text="Food Name").pack()
        name = tk.Entry(self)
        name.pack()
        tk.Label(self, text="Category").pack()
        cat = tk.Entry(self)
        cat.pack()
        tk.Label(self, text="Price").pack()
        price = tk.Entry(self)
        price.pack()
        tk.Label(self, text="Hours till expiry").pack()
        hours = tk.Entry(self)
        hours.pack()

        def add():
            item = FoodItem(name.get(), cat.get(), float(price.get()), self.active_business.id, hours=int(hours.get()))
            self.active_business.listings.append(item)
            food_items.append(item)
            save_data()
            messagebox.showinfo("Success", f"Listed {item.name}")
            self.show_business_menu()

        tk.Button(self, text="Add Food", command=add).pack(pady=5)
        tk.Button(self, text="Back", command=self.show_business_menu).pack(pady=5)

    def view_listings(self):
        self.clear()
        tk.Label(self, text="Your Listings", font=("Arial", 14)).pack(pady=10)
        for item in food_items:
            if item.business_id == self.active_business.id:
                expiry = (item.expiry - dt.datetime.now()).total_seconds() / 3600
                status = f"Expires in {int(expiry)}h" if expiry > 0 else "EXPIRED"
                tk.Label(self, text=f"{item.name} - ${item.price} - {status}").pack()
        tk.Button(self, text="Back", command=self.show_business_menu).pack(pady=5)

    def withdraw(self):
        messagebox.showinfo("Withdraw", f"Withdrawn ${self.active_business.cash:.2f}")
        self.active_business.cash = 0.0
        save_data()
        self.show_business_menu()

if __name__ == '__main__':
    app = App()
    app.mainloop()
