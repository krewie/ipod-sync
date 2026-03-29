from fasthtml.common import *
import pygpod
from pygpod.device.device import Device, StorageInfo, _dir_size, _file_size, _fmt_size
import urllib.parse
from pathlib import Path
from starlette.responses import StreamingResponse, FileResponse
import sys
from urllib.parse import quote
from pathlib import Path

BASE_DIR = Path(__file__).parent

app = FastHTML(
    pico=True,
    hdrs=[
        Link(rel="stylesheet", href="/static/style.css"),
        Link(rel="stylesheet", href="/static/browse.css"),
        Link(rel="stylesheet", href="/static/aquabutton.css"),
        Link(rel="stylesheet", href="/static/showtracks.css"),
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
        A("[ ADD TRACKS ]", href=f"/browse?mountpoint={mountpoint}")
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
                    Div("", cls="browser-item-slot empty"),
                    Div(
                        A(
                            f"📁 {entry.name}",
                            href=f"/browse?folder={urllib.parse.quote(str(entry), safe='')}&mountpoint={urllib.parse.quote(mountpoint, safe='')}"
                        ),
                        cls="browser-item-content"
                    ),
                    cls="browser-item"
                )
            )

        elif entry.suffix.lower() in (".mp3", ".m4a"):
            items.append(
                Li(
                    Div(
                        Button(
                            "[Add]",
                            cls="single-import-btn fancy-button confirm small",
                            **{
                                "data-file": str(entry),
                                "data-mountpoint": mountpoint,
                                "type": "button",
                            }
                        ),
                        cls="browser-item-slot"
                    ),
                    Div(
                        f"🎵 {entry.name}",
                        cls="browser-item-content"
                    ),
                    cls="browser-item"
                )
            )

    parent_folder = folder.parent if folder.parent != folder else folder

    return Div(
        Div(
            Div(f"Browsing: {folder}", cls="browse-current-path"),
            Form(
                Input(
                    type="text",
                    name="folder",
                    value=str(folder),
                    placeholder="Enter folder path"
                ),
                Input(
                    type="hidden",
                    name="mountpoint",
                    value=mountpoint
                ),
                Button("Go", type="submit"),
                action="/browse",
                method="get",
                cls="browse-nav-form"
            ),
            A(
                "[ Up ]",
                href=f"/browse?folder={urllib.parse.quote(str(parent_folder), safe='')}&mountpoint={urllib.parse.quote(mountpoint, safe='')}"
            ),
            A("[ SHOW TRACKS ]", href=f"/showtracks/{mountpoint}"),
            cls="browse-box"
        ),
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
def showtracks(
    mountpoint: str,
    artist: str = "",
    album: str = "",
    genre: str = "",
    song: str = ""
):
    db = pygpod.Database(mountpoint)
    dev = Device.from_mountpoint(mountpoint)
    si = dev.storage_info(full=False)

    tracks = list(db.tracks)

    unique_artists = sorted({t.artist for t in tracks if t.artist})
    unique_albums = sorted({t.album for t in tracks if t.album})
    unique_genres = sorted({t.genre for t in tracks if t.genre})
    unique_songs = sorted({t.title for t in tracks if t.title})

    def matches_filter(track):
        if artist and (track.artist or "") != artist:
            return False
        if album and (track.album or "") != album:
            return False
        if genre and (track.genre or "") != genre:
            return False
        if song and (track.title or "") != song:
            return False
        return True

    filtered_tracks = [t for t in tracks if matches_filter(t)]

    def build_filter_link(filter_name: str, value: str):
        params = {
            "artist": artist,
            "album": album,
            "genre": genre,
            "song": song,
        }

        if params[filter_name] == value:
            params[filter_name] = ""
        else:
            params[filter_name] = value

        query_parts = [f"{k}={quote(v)}" for k, v in params.items() if v]
        query = "&".join(query_parts)

        href = f"/showtracks/{quote(mountpoint, safe='')}"
        if query:
            href += f"?{query}"
        return href

    def filter_section(title: str, values: list[str], filter_name: str, selected_value: str):
        return Div(
            H3(title),
            A(
                "[ clear ]",
                href=build_filter_link(filter_name, selected_value) if selected_value else f"/showtracks/{quote(mountpoint, safe='')}?" + "&".join(
                    f"{k}={quote(v)}"
                    for k, v in {
                        "artist": artist if filter_name != "artist" else "",
                        "album": album if filter_name != "album" else "",
                        "genre": genre if filter_name != "genre" else "",
                        "song": song if filter_name != "song" else "",
                    }.items()
                    if v
                ),
                cls="filter-clear"
            ),
            Ul(
                *[
                    Li(
                        A(
                            value,
                            href=build_filter_link(filter_name, value),
                            cls=f"filter-link{' selected' if value == selected_value else ''}"
                        )
                    )
                    for value in values
                ]
            ),
            cls="filter-column"
        )

    active_filters = Div(
        H3("Active filters"),
        Ul(
            *(
                [Li(f"Artist: {artist}")] if artist else []
            ),
            *(
                [Li(f"Album: {album}")] if album else []
            ),
            *(
                [Li(f"Genre: {genre}")] if genre else []
            ),
            *(
                [Li(f"Song: {song}")] if song else []
            ),
        ) if any([artist, album, genre, song]) else P("None"),
        A(
            "[ clear all ]",
            href=f"/showtracks/{quote(mountpoint, safe='')}",
            cls="filter-clear-all"
        ) if any([artist, album, genre, song]) else "",
        cls="active-filters"
    )

    table = Table(
        Tr(
            Th("ID"),
            Th("has Artwork"),
            Th("Track number"),
            Th("Genre"),
            Th("Title"),
            Th("Artist"),
            Th("Album"),
            Th("Time"),
            Th("Action")
        ),
        *[
            Tr(
                Td(t.track_id),
                Td(t.has_artwork),
                Td(
                    Input(
                        type="number",
                        name="track_number",
                        value=t.track_number or "",
                        hx_post="/updatetrack",
                        hx_trigger="change",
                        hx_include="this",
                        hx_vals={
                            "track_id": t.track_id,
                            "mountpoint": mountpoint,
                            "field": "track_number"
                        },
                        cls="track-input"
                    )
                ),
                Td(
                    Input(
                        type="text",
                        name="genre",
                        value=t.genre or "",
                        hx_post="/updatetrack",
                        hx_trigger="change",
                        hx_include="this",
                        hx_vals={
                            "track_id": t.track_id,
                            "mountpoint": mountpoint,
                            "field": "genre"
                        },
                        cls="track-input"
                    )
                ),
                Td(
                    Input(
                        type="text",
                        name="title",
                        value=t.title or "",
                        hx_post="/updatetrack",
                        hx_trigger="change",
                        hx_include="this",
                        hx_vals={
                            "track_id": t.track_id,
                            "mountpoint": mountpoint,
                            "field": "title"
                        },
                        cls="track-input"
                    )
                ),
                Td(
                    Input(
                        type="text",
                        name="artist",
                        value=t.artist or "",
                        hx_post="/updatetrack",
                        hx_trigger="change",
                        hx_include="this",
                        hx_vals={
                            "track_id": t.track_id,
                            "mountpoint": mountpoint,
                            "field": "artist"
                        },
                        cls="track-input"
                    )
                ),
                Td(
                    Input(
                        type="text",
                        name="album",
                        value=t.album or "",
                        hx_post="/updatetrack",
                        hx_trigger="change",
                        hx_include="this",
                        hx_vals={
                            "track_id": t.track_id,
                            "mountpoint": mountpoint,
                            "field": "album"
                        },
                        cls="track-input"
                    )
                ),
                Td(f"{int(t.duration)//60}:{int(t.duration)%60:02d}"),
                Td(
                    Button(
                        "Remove",
                        cls="fancy-button cancel small",
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
            for t in filtered_tracks
        ],
        cls="tracks-table"
    )

    filters = Div(
        filter_section("Artists", unique_artists, "artist", artist),
        filter_section("Albums", unique_albums, "album", album),
        filter_section("Genres", unique_genres, "genre", genre),
        filter_section("Songs", unique_songs, "song", song),
        cls="filters-row"
    )

    return Div(
        H1("Tracks"),
        H2(f"Total: {si.total / 1_000_000_000:.2f}GB, Used: {si.used / 1_000_000_000:.2f}GB, Free: {si.free / 1_000_000_000:.2f}GB"),
        A("[ DEVICES ]", href="/"),
        " ",
        A("[ ADD TRACKS ]", href=f"/browse?mountpoint={quote(mountpoint, safe='')}"),
        " ",
        A("[ SHOWTRACKS ]", href=f"/showtracks/{quote(mountpoint, safe='')}"),
        Br(), Br(),

        active_filters,
        filters,

        Br(),
        H3(f"Showing {len(filtered_tracks)} of {len(tracks)} tracks"),
        table
    )

#-----------------------------
# Update track
#-----------------------------

def convert_track_field(field: str, value: str):
    if field == "track_number":
        try:
            return int(value) if value != "" else 0
        except ValueError:
            raise ValueError("Invalid track number")

    if field in {"genre", "title", "artist", "album"}:
        return value.strip()

    raise ValueError(f"Invalid field: {field}")

@app.post("/updatetrack")
def updatetrack(track_id: str, mountpoint: str, field: str, data: dict):
    allowed_fields = {"track_number", "genre", "title", "artist", "album"}
    if field not in allowed_fields:
        return "Invalid field", 400

    value = data.get(field, "")

    with pygpod.Database(mountpoint) as db:
        track = next((t for t in db.tracks if str(t.track_id) == str(track_id)), None)
        if track is None:
            return "Track not found", 404

        try:
            converted_value = convert_track_field(field, value)
            setattr(track, field, converted_value)
            db.save()
            return str(getattr(track, field))
        except ValueError:
            return f"Invalid value for {field}", 400
        except Exception as e:
            print(f"Failed to update {field}: {e}")
            return f"Could not update {field}", 400

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