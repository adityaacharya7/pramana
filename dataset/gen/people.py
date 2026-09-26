"""Invented names. Full names are handed out uniquely so the only same-name
pair in the dataset is the one planted on purpose (the two "Rahul Sharma"
records, FX-01)."""
from __future__ import annotations

import random

MALE = [
    "Aditya", "Amit", "Anil", "Arjun", "Ashok", "Deepak", "Dinesh", "Ganesh", "Gopal", "Harish",
    "Imran", "Jatin", "Karan", "Kishore", "Manoj", "Mohit", "Naveen", "Nikhil", "Pankaj", "Prakash",
    "Rajesh", "Ramesh", "Sachin", "Sanjay", "Santosh", "Suresh", "Tarun", "Uday", "Varun", "Vijay",
    "Yusuf", "Abhishek", "Chetan", "Farhan", "Girish", "Hemant", "Irfan", "Joseph", "Lokesh", "Mahendra",
]
FEMALE = [
    "Aarti", "Anjali", "Asha", "Bhavna", "Deepa", "Divya", "Farida", "Geeta", "Hema", "Jyoti",
    "Kavita", "Lata", "Madhuri", "Meena", "Neha", "Nirmala", "Pallavi", "Priya", "Radha", "Rekha",
    "Ritu", "Sadhana", "Sangeeta", "Seema", "Shalini", "Sneha", "Sunita", "Swati", "Usha", "Vandana",
    "Zainab", "Ayesha", "Christina", "Gauri", "Ishita", "Kiran", "Mridula", "Nandini", "Poornima", "Rashmi",
]
SURNAMES = [
    "Agarwal", "Bhatt", "Chatterjee", "Das", "Desai", "Dubey", "Fernandes", "Gupta", "Hegde", "Iyer",
    "Jain", "Joshi", "Kapoor", "Khan", "Kulkarni", "Kumar", "Malhotra", "Menon", "Mishra", "Nair",
    "Naidu", "Pandey", "Patel", "Pillai", "Qureshi", "Rao", "Reddy", "Saxena", "Sethi", "Shaikh",
    "Shetty", "Singh", "Sinha", "Srivastava", "Thakur", "Tiwari", "Varghese", "Verma", "Yadav", "Zaidi",
    "Bose", "Chauhan", "Gowda", "Kamath", "Mehta", "Negi", "Rawat", "Sawant", "Talwar", "Wagh",
]

RESERVED = {
    # Names that appear in the hand-written Tri-City scenario. Kept out of the
    # random pool so the only collisions are the planted ones.
    "Rahul Sharma", "Shobha Kulkarni", "Harish Bhatia", "Kavitha Ramesh", "Sandeep Verma",
    "Pooja Rawat", "Mahesh Agarwal", "Sunita Agarwal", "Aakash Jain", "Nitin Bhatia",
    "Vinod Rathore", "Anil Mehra", "Rakesh Kumar", "Vivek Chauhan", "Neha Kulshreshtha",
    "Sanjay Patil", "Farida Khan", "Arvind Nair", "Meenakshi Iyer", "Suresh Thakur", "Ganesh Yadav",
    "Ritu Negi", "Dinesh Rawat", "Ramesh Verma", "Kamla Verma", "Mohan Sharma", "Rajesh Sharma",
}


class NameGen:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.used: set[str] = set(RESERVED)

    def person(self, gender: str | None = None) -> tuple[str, str]:
        g = gender or self.rng.choice(["M", "F"])
        pool = MALE if g == "M" else FEMALE
        for _ in range(5000):
            name = f"{self.rng.choice(pool)} {self.rng.choice(SURNAMES)}"
            if name not in self.used:
                self.used.add(name)
                return name, g
        raise RuntimeError("name space exhausted")


SHOP_WORDS = ["Kirana", "General Stores", "Provision Store", "Supermart", "Dairy", "Vegetables",
              "Medical Stores", "Bakery", "Fruit Mart", "Departmental Store"]
SHOP_PREFIX = ["Om Sai", "Shree Ganesh", "New Balaji", "Jai Ambe", "Annapurna", "Royal", "Fresh Choice",
               "Lakshmi", "Green Leaf", "Sagar", "Sai Krupa", "Hari Om", "Janata", "Mahalaxmi", "Sunrise",
               "Gokul", "Navkar", "Apna", "Shanti", "Deccan", "Kaveri", "Delhi Darbar", "Anand"]
EMPLOYERS = ["Synthetic Textiles Pvt Ltd", "Demo Logistics LLP", "Sample Infotech Pvt Ltd",
             "Fixture Engineering Works", "Placeholder Pharma Ltd", "Mock Motors Pvt Ltd",
             "Testbed Foods Pvt Ltd", "Sandbox Retail Pvt Ltd", "Dummy Constructions Ltd",
             "Specimen Hospital Trust", "Model School Society", "Prototype Software LLP"]
