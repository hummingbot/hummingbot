import pyautogui as agui
import time
from sys import argv

def main():
    if len(argv) < 5:
        print("usage:")
        print("python3 run_hummingbot.py <hummingbot login> <graphene chain> <graphene wif> <pair>")
        print("Then boot hummingbot in a seperate terminal and cease using your peripherals.")
        exit()
    screen = agui.screenshot()
    width, height = screen.size
    regions_4k = [
        (1700, 900, 2200, 1000),
        (0, 1700, 200, 1900),
        (750, 1700, 1050, 1900),
        (700, 1700, 900, 1900),
        (0, 1700, 200, 1900),
    ]
    regions = []
    for region in regions_4k:
        regions.append(((region[0]/3840)*width, (region[1]/2160)*height, (region[2]/3840)*width, (region[3]/2160)*height))
    while True:
        needle = "login.png"
        a = None
        while a is None:
            haystack = agui.screenshot(region=regions[0])
            time.sleep(2)
            a = agui.locate(needle, haystack, confidence=0.7)
            time.sleep(2)
        agui.write(argv[1])
        agui.press("enter")
        agui.press("enter")

        agui.PAUSE = 0.3


        needle = "prompt.png"
        a = None
        while a is None:
            haystack = agui.screenshot(region=regions[1])
            a = agui.locate(needle, haystack, confidence=0.7)
        agui.write(f"connect {argv[2]}", interval=0.1)
        agui.press("enter")


        a = None
        i = 0
        while a is None:
            i += 1
            haystack = agui.screenshot(region=regions[2])
            a = agui.locate(needle, haystack, confidence=0.7)
            if i > 10:
                break
        if i <= 10:
            agui.write("yes")
            agui.press("enter")

        a = None
        while a is None:
            haystack = agui.screenshot(region=regions[3])
            a = agui.locate(needle, haystack, confidence=0.7)
        agui.write(argv[3])
        agui.press("enter")

        a = None
        while a is None:
            haystack = agui.screenshot(region=regions[4])
            a = agui.locate(needle, haystack, confidence=0.7)
        agui.write("create")
        agui.press("enter")

        agui.write("pure_market_making")
        agui.press("enter")

        agui.write(argv[2])
        agui.press("enter")

        agui.write(argv[4])
        agui.press("enter")


        for _ in range(2):
            agui.write("2")
            agui.press("enter")

        agui.write("120")
        agui.press("enter")

        agui.write("1")
        agui.press("enter")
        agui.press("enter")
        agui.press("enter")
        agui.write("Erase this and continue.")

if __name__ == "__main__":
    main()