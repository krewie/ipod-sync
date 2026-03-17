function renderImportBox() {
    return `
        <div class="import-panel">
            <h3>Importing music to iPod</h3>
            <div class="progress-outer">
                <div id="progressbar" class="progress-inner"></div>
            </div>
            <p id="progresscount"></p>
            <p id="progresssong"></p>
            <p id="progressstatus"></p>
        </div>
    `;
}

function handleStream(url) {
    const box = document.getElementById("importbox");
    if (!box) {
        console.error("Missing #importbox");
        return;
    }

    box.innerHTML = renderImportBox();

    const bar = document.getElementById("progressbar");
    const count = document.getElementById("progresscount");
    const song = document.getElementById("progresssong");
    const status = document.getElementById("progressstatus");

    status.innerText = "Starting import...";

    const source = new EventSource(url);

    source.onmessage = function (e) {
        if (e.data === "done") {
            bar.style.width = "100%";
            status.innerText = "Import complete.";
            source.close();
            return;
        }

        const parts = e.data.split("|");
        if (parts.length < 4) {
            console.error("Unexpected SSE payload:", e.data);
            return;
        }

        const [percent, added, total, name] = parts;

        bar.style.width = percent + "%";
        count.innerText = `${added} / ${total} tracks`;
        song.innerText = `Current: ${name}`;
        status.innerText = "Importing...";
    };

    source.onerror = function (err) {
        console.error("EventSource failed:", err);
        status.innerText = "Import failed.";
        source.close();
    };
}

function startFolderImport(folder, mountpoint) {
    const url =
        `/addfolder?folder=${encodeURIComponent(folder)}` +
        `&mountpoint=${encodeURIComponent(mountpoint)}`;

    handleStream(url);
}

function startSingleImport(file, mountpoint) {
    const url =
        `/addsingle?file=${encodeURIComponent(file)}` +
        `&mountpoint=${encodeURIComponent(mountpoint)}`;

    handleStream(url);
}

function bindImportButtons() {
    const folderBtn = document.getElementById("add-folder-btn");
    if (folderBtn) {
        folderBtn.addEventListener("click", function () {
            startFolderImport(
                this.dataset.folder,
                this.dataset.mountpoint
            );
        });
    }

    document.querySelectorAll(".single-import-btn").forEach((btn) => {
        btn.addEventListener("click", function () {
            startSingleImport(
                this.dataset.file,
                this.dataset.mountpoint
            );
        });
    });
}

document.addEventListener("DOMContentLoaded", bindImportButtons);
document.addEventListener("htmx:afterSwap", bindImportButtons);