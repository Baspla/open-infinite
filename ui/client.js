highestZIndex = 10;
highestButtonIndex = 0;

items = [];
item_buttons = {};
pairCallback = undefined;
usernameCallback = undefined;
searchInput = undefined;
bingoContainer = undefined;
bingoBoard = undefined;
bingoSizeLabel = undefined;
bingoToggle = undefined;
bingoCollapsed = false;
bingoClickCallback = undefined;
timerInterval = null;
stopwatchInterval = null;

function createItem(text_emoji,text_name,x,y,event=undefined,centered=false){
    const item = createItemChip(text_emoji,text_name);
    item.style.zIndex = highestZIndex++;
    document.getElementById('itemWorkspace').appendChild(item);
    if(centered){
        y= (y-item.offsetHeight / 2 )
        x = (x- item.offsetWidth / 2)
    }
        item.style.top = y+ "px";
        item.style.left = x+ "px";
    items.push(item);
    _makeDraggable(item, x, y);
    if(event!==undefined){
        item.onmousedown(event);
    }
}

function createItemChip(text_emoji,text_name){
    chip = document.createElement('div')
    chip.name = text_name;
    chip.emoji = text_emoji;
    chip.dataset.searchText = `${text_name} ${text_emoji}`.toLowerCase();
    chip.className='transition-transform hover:bg-[linear-gradient(180deg,#d6fcff,#fff_90%)] outline-[#7eb1ce] p-[10px] rounded-[5px] cursor-pointer bg-[#fff] text-[18px] leading-[1em] dark:bg-[#000] dark:text-[#fff] dark:hover:bg-[linear-gradient(180deg,#6acbe182,#000_90%)] dark:outline-[#666] outline outline-1'
    const emoji = document.createElement('span');
    emoji.className = 'text-[21px] mr-1';
    emoji.innerText = text_emoji;
    const name = document.createElement('span')
    name.className = 'name'
    name.innerText = text_name
    chip.appendChild(emoji)
    chip.appendChild(name)
    return chip;
}

function createItemButton(text_emoji,text_name){
    if(text_name in item_buttons){
        return;
    }
    list = document.getElementById('item-list')
    const itemButton = createItemChip(text_emoji,text_name);
    itemButton.id = "itemButton"+highestButtonIndex++;
    itemButton.addEventListener('mousedown', function(event){
        if(event.button !== 0){
            return;
        }
        const workspace = document.getElementById('canvas') || document.getElementById('itemWorkspace');
        let targetX = event.clientX;
        let targetY = event.clientY;

        if(workspace){
            const rect = workspace.getBoundingClientRect();
            targetX = rect.left + rect.width / 2;
            targetY = rect.top + rect.height / 2;
        }

        // Spawn centered in the main field instead of where the sidebar is clicked.
        createItem(text_emoji, text_name, targetX, targetY, undefined, true);
    })
    item_buttons[text_name] = itemButton;
    list.appendChild(itemButton);
    applyItemFilter();
}

function initClient(callbackPair, callbackUsername, callbackBingoClick){
    pairCallback = callbackPair;
    usernameCallback = callbackUsername;
    bingoClickCallback = callbackBingoClick;
    createItemButton("🚧","Kaputt")
    createItemButton("🔗","Verbindung")
    createItemButton("💻","Server")
    initCanvas();
    initButtons();
    initSearch();
    initBingoUI();
}

function clearItems(){
    items.forEach(function(item){
        removeItem(item);
    })
}

function initButtons(){
    const clear = document.getElementById('btn-clear');
    clear.addEventListener('click', clearItems);
    const rename = document.getElementById('btn-rename');
    rename.classList.add('hidden');
}

function initSearch(){
    searchInput = document.getElementById('item-search');
    if(!searchInput){
        return;
    }
    searchInput.addEventListener('input', applyItemFilter);
}

function initBingoUI(){
    bingoContainer = document.getElementById('bingo-container');
    bingoBoard = document.getElementById('bingo-board');
    bingoSizeLabel = document.getElementById('bingo-size');
    bingoToggle = document.getElementById('bingo-toggle');
    if(!bingoContainer || !bingoBoard || !bingoToggle){
        return;
    }
    bingoToggle.addEventListener('click', function(){
        bingoCollapsed = !bingoCollapsed;
        bingoBoard.classList.toggle('hidden', bingoCollapsed);
        bingoToggle.innerText = bingoCollapsed ? 'Einblenden' : 'Ausblenden';
    });
}

function updateUserList(users){
    const container = document.getElementById('player-container');
    const list = document.getElementById('player-list');
    if(!container || !list){
        return;
    }

    if(!users || !Array.isArray(users) || users.length === 0){
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    list.innerHTML = '';

    users.forEach(user => {
        const item = document.createElement('div');
        item.className = 'flex items-center gap-2 p-2 rounded bg-white dark:bg-[#1a1a1a] border border-[#a3a3a3] dark:border-[#2a2a2a] shrink-0';
        
        const dot = document.createElement('div');
        dot.className = 'w-3 h-3 rounded-full';
        dot.style.backgroundColor = user.color || '#888';
        
        const name = document.createElement('span');
        name.className = 'text-sm font-medium';
        name.innerText = user.name || 'Unbekannt';
        
        item.appendChild(dot);
        item.appendChild(name);
        list.appendChild(item);
    });
}

function setBingoField(field){
    if(!bingoContainer || !bingoBoard){
        console.log("Bingo UI not initialized");
        return;
    }
    if(!field || ![2,3,4,5].includes(field.size) || !Array.isArray(field.cells)){
        bingoContainer.classList.add('hidden');
        bingoBoard.innerHTML = '';
        if(bingoSizeLabel){
            bingoSizeLabel.innerText = '';
        }
        console.log("Invalid bingo field data", field);
        return;
    }

    bingoContainer.classList.remove('hidden');
    bingoBoard.innerHTML = '';
    bingoBoard.style.gridTemplateColumns = `repeat(${field.size}, minmax(0, 1fr))`;
    if(bingoSizeLabel){
        bingoSizeLabel.innerText = `${field.size} x ${field.size}`;
    }

    const total = field.size * field.size;

    function normalizeHex(color){
        if(typeof color !== 'string'){
            return null;
        }
        let hex = color.trim();
        if(hex.startsWith('#')){
            hex = hex.slice(1);
        }
        if(hex.length === 3){
            hex = hex.split('').map(c => c + c).join('');
        }
        if(!/^([0-9a-fA-F]{6})$/.test(hex)){
            return null;
        }
        return `#${hex.toLowerCase()}`;
    }

    function hexToRgba(hex, alpha){
        const clean = hex.slice(1);
        const r = parseInt(clean.slice(0,2), 16);
        const g = parseInt(clean.slice(2,4), 16);
        const b = parseInt(clean.slice(4,6), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    for(let i = 0; i < total; i++){
        const cellData = field.cells[i] || {};
        const cell = document.createElement('div');
        cell.className = 'rounded border border-[#a3a3a3] dark:border-gray-700 bg-white dark:bg-gray-900 p-3 text-center text-base leading-tight break-all min-h-14 flex items-center justify-center';
        
        const validColors = (Array.isArray(cellData.done_colors) ? cellData.done_colors : [])
            .map(normalizeHex)
            .filter(c => c);

        if (validColors.length > 0) {
            cell.classList.add('line-through');
            if (validColors.length === 1) {
                const c = validColors[0];
                cell.style.backgroundColor = hexToRgba(c, 0.25);
                cell.style.borderColor = c;
                cell.style.borderWidth = '2px';
            } else {
                const stops = validColors.map((c, idx) => {
                    const pct = 100 / validColors.length;
                    const start = idx * pct;
                    const end = (idx + 1) * pct;
                    return `${hexToRgba(c, 0.25)} ${start}%, ${hexToRgba(c, 0.25)} ${end}%`;
                }).join(', ');
                cell.style.background = `linear-gradient(135deg, ${stops})`;
            }
        } else if (cellData.done) {
            cell.classList.add('line-through');
            cell.classList.add('bg-green-100');
            cell.classList.add('dark:bg-green-900');
        }

        cell.innerText = cellData.text || '';
        if(typeof bingoClickCallback === 'function'){
            const row = Math.floor(i / field.size);
            const col = i % field.size;
            cell.addEventListener('click', function(){
                bingoClickCallback({
                    index: i,
                    row,
                    col,
                    size: field.size,
                    text: cellData.text || '',
                });
            });
        }
        bingoBoard.appendChild(cell);
    }

    bingoBoard.classList.toggle('hidden', bingoCollapsed);
    if(bingoToggle){
        bingoToggle.innerText = bingoCollapsed ? 'Einblenden' : 'Ausblenden';
    }
}

function hideBingo(){
    if(!bingoContainer || !bingoBoard){
        return;
    }
    bingoContainer.classList.add('hidden');
    bingoBoard.innerHTML = '';
    if(bingoSizeLabel){
        bingoSizeLabel.innerText = '';
    }
}

function applyItemFilter(){
    const query = (searchInput?.value || '').trim().toLowerCase();
    Object.values(item_buttons).forEach((button) => {
        const haystack = button.dataset.searchText || button.innerText.toLowerCase();
        const matches = query === '' || haystack.includes(query);
        button.classList.toggle('hidden', !matches);
    });
}

function initCanvas(){
    const canvas = document.getElementById('canvas');
    if(!canvas){
        return;
    }

    const ctx = canvas.getContext('2d');

    const baseWidth = 5120;
    const baseHeight = 2160;
    const particleCount = 60;
    const linkDistance = 90;
    const maxLineOpacity = 0.45;
    const dotRadius = 2;
    const maxSpeed = 0.015; // px per ms in the virtual space
    const cursorLineBoost = 1.3;

    const particles = Array.from({length: particleCount}, () => ({
        x: Math.random() * baseWidth,
        y: Math.random() * baseHeight,
        vx: (Math.random() - 0.5) * maxSpeed,
        vy: (Math.random() - 0.5) * maxSpeed,
        dotOpacity: 0.35 + Math.random() * 0.65,
    }));

    let lastTimestamp = 0;
    let mousePos = null;

    function getItemAnchors(){
        const rect = canvas.getBoundingClientRect();
        return items
            .map((item) => {
                const itemRect = item.getBoundingClientRect();
                const anchor = {
                    x: itemRect.left + itemRect.width / 2 - rect.left,
                    y: itemRect.top + itemRect.height / 2 - rect.top,
                };
                const visible =
                    anchor.x >= -linkDistance && anchor.x <= rect.width + linkDistance &&
                    anchor.y >= -linkDistance && anchor.y <= rect.height + linkDistance;
                return visible ? anchor : null;
            })
            .filter(Boolean);
    }

    function isDarkMode(){
        return document.documentElement.classList.contains('dark') ||
            (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    }

    function palette(){
        const dark = isDarkMode();
        return {
            dot: (opacity = 1) => dark
                ? `rgba(255,255,255,${0.85 * opacity})`
                : `rgba(55,65,81,${0.8 * opacity})`,
            line: (opacity) => dark
                ? `rgba(255,255,255,${opacity})`
                : `rgba(55,65,81,${opacity})`,
        };
    }

    function resizeCanvas(){
        const rect = canvas.getBoundingClientRect();
        const ratio = window.devicePixelRatio || 1;
        canvas.width = rect.width * ratio;
        canvas.height = rect.height * ratio;
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function update(deltaMs){
        for (const p of particles){
            p.x = (p.x + p.vx * deltaMs + baseWidth) % baseWidth;
            p.y = (p.y + p.vy * deltaMs + baseHeight) % baseHeight;
        }
    }

    function draw(){
        const ratio = window.devicePixelRatio || 1;
        const width = canvas.width / ratio;
        const height = canvas.height / ratio;
        const colors = palette();

        ctx.clearRect(0, 0, width, height);

        const projected = particles.map(p => ({
            x: p.x % width,
            y: p.y % height,
        }));

        const anchors = getItemAnchors();

        ctx.lineWidth = 1;
        for(let i = 0; i < projected.length; i++){
            const a = projected[i];
            for(let j = i + 1; j < projected.length; j++){
                const b = projected[j];
                const dx = a.x - b.x;
                const dy = a.y - b.y;
                const dist = Math.hypot(dx, dy);
                if(dist > linkDistance){
                    continue;
                }
                const opacity = (1 - dist / linkDistance) * maxLineOpacity;
                ctx.strokeStyle = colors.line(opacity);
                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.stroke();
            }
        }

        for(let idx = 0; idx < projected.length; idx++){
            const p = projected[idx];
            ctx.fillStyle = colors.dot(particles[idx].dotOpacity);
            ctx.beginPath();
            ctx.arc(p.x, p.y, dotRadius, 0, Math.PI * 2);
            ctx.fill();
        }

        // Connect draggable items to nearby dots
        for(let i = 0; i < anchors.length; i++){
            const anchor = anchors[i];
            for(let idx = 0; idx < projected.length; idx++){
                const p = projected[idx];
                const dx = anchor.x - p.x;
                const dy = anchor.y - p.y;
                const dist = Math.hypot(dx, dy);
                if(dist > linkDistance){
                    continue;
                }
                const opacity = (1 - dist / linkDistance) * maxLineOpacity;
                ctx.strokeStyle = colors.line(opacity);
                ctx.beginPath();
                ctx.moveTo(anchor.x, anchor.y);
                ctx.lineTo(p.x, p.y);
                ctx.stroke();
            }
            // Connect draggable items to each other
            for(let j = 0; j < anchors.length; j++){
                const other = anchors[j];
                if(j <= i){
                    continue;
                }
                const dx = anchor.x - other.x;
                const dy = anchor.y - other.y;
                const dist = Math.hypot(dx, dy);
                if(dist > linkDistance){
                    continue;
                }
                const opacity = (1 - dist / linkDistance) * maxLineOpacity;
                ctx.strokeStyle = colors.line(opacity);
                ctx.beginPath();
                ctx.moveTo(anchor.x, anchor.y);
                ctx.lineTo(other.x, other.y);
                ctx.stroke();
            }
            ctx.fillStyle = colors.dot(0.9);
            ctx.beginPath();
            ctx.arc(anchor.x, anchor.y, dotRadius, 0, Math.PI * 2);
            ctx.fill();
        }

        if(mousePos){
            // Connect cursor to nearby dots
            for(const p of projected){
                const dx = mousePos.x - p.x;
                const dy = mousePos.y - p.y;
                const dist = Math.hypot(dx, dy);
                if(dist > linkDistance){
                    continue;
                }
                const opacity = Math.min(1, (1 - dist / linkDistance) * maxLineOpacity * cursorLineBoost);
                ctx.strokeStyle = colors.line(opacity);
                ctx.beginPath();
                ctx.moveTo(mousePos.x, mousePos.y);
                ctx.lineTo(p.x, p.y);
                ctx.stroke();
            }
        }
    }

    function loop(timestamp){
        const delta = lastTimestamp ? (timestamp - lastTimestamp) : 16;
        lastTimestamp = timestamp;
        update(delta);
        draw();
        requestAnimationFrame(loop);
    }

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    canvas.addEventListener('mousemove', (event) => {
        const rect = canvas.getBoundingClientRect();
        mousePos = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
        };
    });

    canvas.addEventListener('mouseleave', () => {
        mousePos = null;
    });
    requestAnimationFrame(loop);
}

function setStatus(text){
    document.getElementById("status").innerText = text;
}

function setUsername(text){
    let elem = document.getElementById("username")
    elem.innerText = text;
    elem.classList.remove('hidden');
}

function setNews(text){
    document.getElementById("news").innerText = text;
}

function setTimer(seconds){
    const elem = document.getElementById("timer");
    if(!elem) return; // fail safe
    
    // Clear any previous interval
    if(timerInterval !== null){
        clearInterval(timerInterval);
        timerInterval = null;
    }

    if(seconds <= 0){
        elem.classList.add('hidden');
        return;
    }

    elem.classList.remove('hidden');
    
    let currentSeconds = seconds;
    
    function update(){
        if(currentSeconds < 0){
            elem.innerText = "00:00";
            // Optional: hide it or keep it at 00:00
            // elem.classList.add('hidden');
            if(timerInterval) clearInterval(timerInterval);
            return;
        }
        const m = Math.floor(currentSeconds / 60);
        const s = currentSeconds % 60;
        const mm = m < 10 ? "0" + m : m;
        const ss = s < 10 ? "0" + s : s;
        elem.innerText = `${mm}:${ss}`;
        currentSeconds--;
    }
    
    update();
    timerInterval = setInterval(update, 1000);
}

function setStopwatch(state){
    const elem = document.getElementById('stopwatch');
    if(!elem){
        return;
    }

    if(stopwatchInterval !== null){
        clearInterval(stopwatchInterval);
        stopwatchInterval = null;
    }

    const seconds = Math.max(0, Math.floor(state?.seconds ?? 0));
    const running = !!state?.running;

    if(!state || typeof state.seconds !== 'number'){
        elem.classList.add('hidden');
        return;
    }

    const formatTime = (totalSeconds) => {
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const secs = totalSeconds % 60;
        const hh = hours > 0 ? String(hours).padStart(2, '0') + ':' : '';
        const mm = String(minutes).padStart(2, '0');
        const ss = String(secs).padStart(2, '0');
        return `${hh}${mm}:${ss}`;
    };

    elem.classList.remove('hidden');

    const startedAt = Date.now();
    const render = () => {
        const elapsed = running ? Math.floor((Date.now() - startedAt) / 1000) : 0;
        elem.innerText = formatTime(seconds + elapsed);
    };

    render();
    if(running){
        stopwatchInterval = setInterval(render, 1000);
    }
}

//
// Interne Funktionen
//

function _getPair(item1, item2){
    if (pairCallback === undefined){
        return;
    }
    item1.pairing = true;
    item2.pairing = true;
    item1.classList.add('opacity-50');
    item1.classList.add('hover:bg-none');
    item1.classList.add('dark:hover:bg-none');
    item1.classList.add('cursor-default');
    item2.classList.add('opacity-50');
    item2.classList.add('hover:bg-none');
    item2.classList.add('dark:hover:bg-none');
    item2.classList.add('cursor-default');
    if(!pairCallback(item1, item2)){
        item1.pairing = false;
        item2.pairing = false;
        item1.classList.remove('opacity-50');
        item1.classList.remove('hover:bg-none');
        item1.classList.remove('dark:hover:bg-none');
        item1.classList.remove('cursor-default');
        item2.classList.remove('opacity-50');
        item2.classList.remove('hover:bg-none');
        item2.classList.remove('dark:hover:bg-none');
        item2.classList.remove('cursor-default');
    
    }
}

// Überprüft ob zwei Bounds sich überschneiden
function _doesOverlap(a, b){
    return (
        a.left < b.right &&
        a.right > b.left &&
        a.top < b.bottom &&
        a.bottom > b.top
    );
}

// Berechnet das nähste Item und gibt es zurück
function _findClosestItem(item, maxDistance){
    let closest = null;
    let closestDistance = Infinity;
    let bounds = item.getBoundingClientRect();
    for(let i = 0; i < items.length; i++){
        if(item !== items[i]){
            const distance = Math.sqrt(
                Math.pow(item.offsetLeft - items[i].offsetLeft, 2) +
                Math.pow(item.offsetTop - items[i].offsetTop, 2)
            );
            if(distance < closestDistance&&items[i].pairing === false){
                closestDistance = distance;
                closest = items[i];
            }
        }
    }
    if(closestDistance > maxDistance){
        return null;
    }
    closestBounds = closest.getBoundingClientRect();
    if(_doesOverlap(bounds, closestBounds)&&closest.pairing === false){
        return closest;
    }else{
        return null;
    }
}

function removeItem(elem){
    elem.remove();
    items = items.filter(function(item){
        return item !== elem;
    });

}

function _makeDraggable(item, pos_3=0, pos_4=0) {
    let pos1=0, pos2=0, pos3= pos_3, pos4= pos_4;
    let startx = 0;
    let starty = 0;
    let hasDragged = false; // tracks whether the pointer moved during this drag
    let lastClosest = null;
    item.pairing = false;
    item.new = true;
    item.onmousedown = dragMouseDown;
    item.onmousemove = forwardMoveToCanvas;
    item.oncontextmenu = function(e){
        if (item.pairing){
            return;
        }
        e.preventDefault();
        removeItem(item);
    }
    item.classList.add('absolute');

    function forwardMoveToCanvas(e){
        const canvas = document.getElementById('canvas');
        canvas.dispatchEvent(new MouseEvent('mousemove', {
            clientX: e.clientX,
            clientY: e.clientY
        }));
    }

    function dragMouseDown(e) {
        if (item.pairing){
            return;
        }
        e.preventDefault();
        if(e.button === 1&&!item.new){
            createItem(item.emoji, item.name, e.clientX, e.clientY, e, true);
            return;
        }
        if(e.button !== 0){
            return;
        }
        if(e.detail === 2&&!item.new){ // Doppelklick wird bei neuen Items ignoriert um nicht unendlich viele Items zu erstellen
            createItem(item.emoji, item.name, e.clientX, e.clientY, e, true);
            return;
        }
        item.new = false;

        item.style.zIndex = highestZIndex++;
        // Startpositionen bekommen
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        // Während der Bewegung aufrufen
        document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        e.preventDefault();
        hasDragged = true;
        // Neue Position berechnen
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        if(startx < 10 && starty < 10 && startx > -10 && starty > -10){
            startx += pos1;
            starty += pos2;
        }
        // Elemente neue Position setzen
        item.style.top = (item.offsetTop - pos2) + "px";
        item.style.left = (item.offsetLeft - pos1) + "px";
        // Wenn das Item ein anderes Item berührt, dann beide Farblich markieren
        let closest = _findClosestItem(item, 400);
        highlightWith(closest);
        forwardMoveToCanvas(e);
    }

    function highlightWith(closest){
        if(lastClosest !== closest){
            if(lastClosest !== null){
                lastClosest.classList.remove('scale-105');
                lastClosest.classList.remove('bg-[linear-gradient(180deg,#d6fcff,#fff_90%)]');
                lastClosest.classList.remove('dark:bg-[linear-gradient(180deg,#6acbe182,#000_90%)]');
            }
            if(closest !== null){
                closest.classList.add('scale-105');
                closest.classList.add('bg-[linear-gradient(180deg,#d6fcff,#fff_90%)]');
                closest.classList.add('dark:bg-[linear-gradient(180deg,#6acbe182,#000_90%)]');
            }
            lastClosest = closest;
        }
    }

    function closeDragElement() {
        // Beenden des Ziehens
        document.onmouseup = null;
        document.onmousemove = null;
        if (!hasDragged) {
            highlightWith(null);
            return; // pure click: keep the item
        }
        // Prüfen ob das item über der Itemliste abgelegt wurde. Wenn ja, dann wird es gelöscht
        itemList = document.getElementById('item-destroybox');
        if(_doesOverlap(item.getBoundingClientRect(), itemList.getBoundingClientRect())){
            removeItem(item);
            return;
        }

        if(lastClosest !== null){
           _getPair(item, lastClosest)
        }
        highlightWith(null);
    }
}

