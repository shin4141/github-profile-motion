"""Original, small, high-contrast demo icons; users may supply any PNG instead."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
S = 4


def save(name, draw_icon):
    im = Image.new("RGBA", (64*S, 64*S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    draw_icon(d)
    im.resize((64, 64), Image.Resampling.LANCZOS).save(ROOT / name)


def cat(d):
    # Original rounded black cat: broad quiet face, tiny body, no bow.
    ink, edge = "#080d18", "#d5e1eb"
    d.arc((43*S, 39*S, 65*S, 62*S), 15, 285, fill=edge, width=7*S)
    d.arc((43*S, 39*S, 65*S, 62*S), 15, 285, fill=ink, width=5*S)
    d.ellipse((21*S, 45*S, 43*S, 63*S), fill=ink, outline=edge, width=2*S)
    d.ellipse((16*S, 55*S, 27*S, 63*S), fill=ink, outline=edge, width=S)
    d.ellipse((37*S, 55*S, 48*S, 63*S), fill=ink, outline=edge, width=S)
    d.polygon([(9*S, 26*S), (10*S, 10*S), (24*S, 21*S)], fill=ink, outline=edge, width=2*S)
    d.polygon([(40*S, 21*S), (54*S, 10*S), (55*S, 26*S)], fill=ink, outline=edge, width=2*S)
    d.polygon([(13*S, 19*S), (14*S, 15*S), (19*S, 20*S)], fill="#69617e")
    d.polygon([(45*S, 20*S), (50*S, 15*S), (51*S, 19*S)], fill="#69617e")
    d.ellipse((5*S, 16*S, 59*S, 57*S), fill=ink, outline=edge, width=2*S)
    d.ellipse((19*S, 36*S, 23*S, 40*S), fill="#d9fff4")
    d.ellipse((41*S, 36*S, 45*S, 40*S), fill="#d9fff4")
    d.ellipse((30*S, 44*S, 34*S, 47*S), fill="#f3c4bc")
    d.arc((27*S, 46*S, 32*S, 51*S), 10, 135, fill="#cbdde5", width=S)
    d.arc((32*S, 46*S, 37*S, 51*S), 45, 170, fill="#cbdde5", width=S)
    crown(d, 22, 2)


def crown(d, x, y):
    """Small rounded gold crown, deliberately distinct from any bow."""
    gold, edge = "#fbd576", "#94673b"
    d.polygon([((x+1)*S, (y+12)*S), ((x+3)*S, (y+5)*S),
               ((x+7)*S, (y+9)*S), ((x+10)*S, (y+2)*S),
               ((x+14)*S, (y+9)*S), ((x+18)*S, (y+5)*S),
               ((x+20)*S, (y+12)*S)], fill=gold, outline=edge, width=S)
    for dx, dy in ((3, 5), (10, 2), (18, 5)):
        d.ellipse(((x+dx-2)*S, (y+dy-2)*S,
                   (x+dx+2)*S, (y+dy+2)*S), fill=gold, outline=edge, width=S)
    d.rounded_rectangle(((x+1)*S, (y+11)*S, (x+20)*S, (y+17)*S),
                        radius=2*S, fill=gold, outline=edge, width=S)


def fox(d):
    d.polygon([(5*S, 7*S), (19*S, 20*S), (32*S, 18*S), (45*S, 20*S), (59*S, 7*S), (54*S, 45*S), (43*S, 60*S), (21*S, 60*S), (10*S, 45*S)], fill="#f08152", outline="#582d39", width=2*S)
    d.polygon([(13*S, 14*S), (20*S, 26*S), (17*S, 33*S)], fill="#ffdbbd")
    d.polygon([(51*S, 14*S), (44*S, 26*S), (47*S, 33*S)], fill="#ffdbbd")
    d.polygon([(9*S, 40*S), (28*S, 47*S), (32*S, 54*S), (36*S, 47*S), (55*S, 40*S), (43*S, 60*S), (21*S, 60*S)], fill="#fff1dd")
    d.ellipse((20*S, 36*S, 26*S, 41*S), fill="#25203b")
    d.ellipse((38*S, 36*S, 44*S, 41*S), fill="#25203b")
    d.polygon([(28*S, 48*S), (36*S, 48*S), (32*S, 53*S)], fill="#392739")


def cat_sleep(d):
    # Curled ball with the same large face and small closed eyes.
    ink, edge = "#080d18", "#d5e1eb"
    d.ellipse((20*S, 25*S, 60*S, 62*S), fill=ink, outline=edge, width=2*S)
    d.arc((38*S, 32*S, 63*S, 62*S), 35, 295, fill=edge, width=6*S)
    d.arc((38*S, 32*S, 63*S, 62*S), 35, 295, fill=ink, width=4*S)
    d.polygon([(6*S, 29*S), (8*S, 14*S), (20*S, 25*S)], fill=ink, outline=edge, width=2*S)
    d.polygon([(27*S, 24*S), (36*S, 13*S), (38*S, 30*S)], fill=ink, outline=edge, width=2*S)
    d.ellipse((4*S, 22*S, 42*S, 57*S), fill=ink, outline=edge, width=2*S)
    d.arc((11*S, 36*S, 18*S, 44*S), 10, 165, fill="#d9fff4", width=2*S)
    d.arc((27*S, 36*S, 34*S, 44*S), 10, 165, fill="#d9fff4", width=2*S)
    d.ellipse((21*S, 45*S, 25*S, 48*S), fill="#f3c4bc")
    d.ellipse((16*S, 54*S, 29*S, 62*S), fill=ink, outline=edge, width=S)
    crown(d, 10, 8)


def cat_waking(d):
    cat(d)
    # A single tiny stretch and half-lidded eyes, not a second animation rig.
    d.ellipse((19*S, 35*S, 24*S, 41*S), fill="#080d18")
    d.ellipse((40*S, 35*S, 46*S, 41*S), fill="#080d18")
    d.arc((19*S, 36*S, 24*S, 42*S), 5, 165, fill="#d9fff4", width=2*S)
    d.arc((40*S, 36*S, 46*S, 42*S), 5, 165, fill="#d9fff4", width=2*S)
    d.line((44*S, 57*S, 54*S, 49*S), fill="#d5e1eb", width=7*S)
    d.line((44*S, 57*S, 54*S, 49*S), fill="#080d18", width=5*S)
    d.ellipse((51*S, 45*S, 60*S, 52*S), fill="#080d18", outline="#d5e1eb", width=S)


if __name__ == "__main__":
    save("crowned_cat.png", cat)
    save("crowned_cat_sleep.png", cat_sleep)
    save("crowned_cat_waking.png", cat_waking)
    save("fox.png", fox)
