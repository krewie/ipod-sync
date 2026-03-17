from fasthtml.common import *
import pygpod
import urllib.parse
from pathlib import Path
from starlette.responses import StreamingResponse, FileResponse
import sys

BASE_DIR = Path(__file__).parent

app = FastHTML(
    pico=True,
    hdrs=[
        Link(rel="stylesheet", href="/static/style.css"),
        Script(src="/static/app.js", defer=True)
    ]
)

# ----------------------------
# Static files
# ----------------------------

@app.get("/static/{fname:path}")
def static(fname: str):
    return FileResponse(BASE_DIR / "static" / fname)


# ----------------------------
# Home
# ----------------------------

@app.route("/")
def home():

    discoverables = pygpod.discover()

    items = [
        Li(
            A(
                d[1].model,
                href=f"/ipod/{urllib.parse.quote(d[0], safe='')}"
            )
        )
        for d in discoverables
    ]

    return Div(
        H1("Discoverable Ipods"),
        Ul(*items)
    )


# ----------------------------
# Device page
# ----------------------------

@app.route("/ipod/{mountpoint:path}")
def ipod(mountpoint: str):
    
    return Div(
        A("[ DEVICES ]", href="/"),
        Br(), Br(),
        A("[ SHOW TRACKS ]", href=f"/showtracks/{mountpoint}"),
        Br(), Br(),
        A("[ ADD TRACKS ]", href=f"/addtracks/{mountpoint}")
    )


# ----------------------------
# Add tracks menu
# ----------------------------

@app.route("/addtracks/{mountpoint:path}")
def addtracks(mountpoint: str):

    return Div(
        H1("Add Tracks"),
        A("Browse Music", href=f"/browse?mountpoint={mountpoint}")
    )


# ----------------------------
# File browser
# ----------------------------

@app.route("/browse")
def browse(folder: str = "~/Music", mountpoint: str = ""):

    folder = Path(folder).expanduser()

    items = []

    for entry in sorted(folder.iterdir()):

        if entry.is_dir():
            items.append(
                Li(
                    A(
                        f"📁 {entry.name}",
                        href=f"/browse?folder={urllib.parse.quote(str(entry), safe='')}&mountpoint={urllib.parse.quote(mountpoint, safe='')}"
                    )
                )
            )

        elif entry.suffix.lower() in (".mp3", ".m4a"):
            items.append(
                Li(
                    f"🎵 {entry.name} ",
                    Button(
                        "[Add]",
                        cls="single-import-btn",
                        **{
                            "data-file": str(entry),
                            "data-mountpoint": mountpoint,
                            "type": "button",
                        }
                    )
                )
            )

    return Div(
        H2(f"Browsing: {folder}"),
        A("[ SHOW TRACKS ]", href=f"/showtracks/{mountpoint}"),
        Br(),
        Br(),
        Button(
            "Add All Music Files",
            id="add-folder-btn",
            type="button",
            **{
                "data-folder": str(folder),
                "data-mountpoint": mountpoint,
            }
        ),
        Br(),
        Br(),
        Div(id="importbox"),
        Ul(*items)
    )

# ----------------------------
# Folder import (stream)
# ----------------------------

@app.get("/addfolder")
def addfolder(folder: str, mountpoint: str):

    folder = Path(folder)

    music_files = []

    for ext in ("*.mp3", "*.m4a"):
        music_files.extend(folder.rglob(ext))

    music_files = sorted(music_files, key=lambda p: (str(p.parent), p.name.lower()))

    total = len(music_files)

    def generate():

        added = 0

        with pygpod.Database(mountpoint) as db:

            for song in music_files:

                db.add_track(song)

                added += 1
                percent = int((added / total) * 100)

                yield f"data: {percent}|{added}|{total}|{song.name}\n\n"

        yield "data: done\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ----------------------------
# Single file import (stream)
# ----------------------------

@app.get("/addsingle")
def addsingle(file: str, mountpoint: str):

    file = Path(file)

    def generate():

        with pygpod.Database(mountpoint) as db:

            db.add_track(file)

            yield f"data: 100|1|1|{file.name}\n\n"

        yield "data: done\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ----------------------------
# Show tracks
# ----------------------------

@app.route("/showtracks/{mountpoint:path}")
def showtracks(mountpoint: str):

    db = pygpod.Database(mountpoint)

    table = Table(

        Tr(
            Th("ID"),
            Th("Title"),
            Th("Artist"),
            Th("Album"),
            Th("Time"),
            Th("Action")
        ),

        *[
            Tr(
                Td(t.track_id),
                Td(t.title),
                Td(t.artist),
                Td(t.album),
                Td(f"{int(t.duration)//60}:{int(t.duration)%60:02d}"),

                Td(
                    Button(
                        "Remove",
                        hx_post="/removetrack",
                        hx_vals={
                            "track_id": t.track_id,
                            "mountpoint": mountpoint
                        },
                        hx_target="closest tr",
                        hx_swap="outerHTML"
                    )
                )
            )
            for t in db.tracks
        ]
    )

    return Div(
        H1("Tracks"),
        A("[ DEVICES ]", href="/"),
        A("[ ADD TRACKS ]", href=f"/addtracks/{mountpoint}"),
        Br(), Br(),
        table
    )


# ----------------------------
# Remove track
# ----------------------------

@app.post("/removetrack")
def removetrack(track_id: int, mountpoint: str):

    with pygpod.Database(mountpoint) as db:

        track = db.get_track(track_id)

        if not track:
            print(f"Track {track_id} not found", file=sys.stderr)
            return ""

        db.remove_track(track, delete_file=True)

    return ""


# ----------------------------
# Run
# ----------------------------

serve()