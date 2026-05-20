_DEMO = [
    {"id": "cl_1", "name": "TOO ABC",   "bin": "123456789012", "phone": "+7 701 000 0001"},
    {"id": "cl_2", "name": "ИП Иванов", "bin": "987654321098", "phone": "+7 705 000 0002"},
    {"id": "cl_3", "name": "TOO Beta",  "bin": "555555555555", "phone": "+7 707 000 0003"},
    {"id": "cl_4", "name": "TOO Gamma", "bin": "111122223333", "phone": "+7 700 000 0004"},
]


class ClientService:
    def list_demo(self): return _DEMO
