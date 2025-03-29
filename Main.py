
from EbzDD3 import EbzDD3

def Main() -> None:

    em = EbzDD3()
    info = em.ReceiveInfo(0)
    print("Zähler 1")
    EbzDD3.PrintInfo(info)

    print()
    
    info = em.ReceiveInfo(1)
    print("Zähler 2")
    EbzDD3.PrintInfo(info)

if __name__ == "__main__":
    Main()
    
