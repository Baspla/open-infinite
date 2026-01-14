highestZIndex = 10;
highestButtonIndex = 0;

items = [];
item_buttons = {};
pairCallback = undefined;
usernameCallback = undefined;

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
    chip.className='transition-transform hover:bg-[linear-gradient(0deg,#d6fcff,#fff_90%)] outline-[#7eb1ce] p-[10px] rounded-[5px] cursor-pointer bg-[#fff] text-[18px] leading-[1em] dark:bg-[#000] dark:text-[#fff] dark:hover:bg-[linear-gradient(0deg,#6acbe182,#000_90%)] dark:outline-[#666] outline outline-1'
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
        createItem(text_emoji,text_name,event.clientX,event.clientY, event, true);
    })
    item_buttons[text_name] = itemButton;
    list.appendChild(itemButton);
}

function initClient(callbackPair, callbackUsername){
    pairCallback = callbackPair;
    usernameCallback = callbackUsername;
    createItemButton("🚧","Kaputt")
    createItemButton("🔗","Verbindung")
    createItemButton("💻","Server")
    initCanvas();
    initButtons();
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

function initCanvas(){
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');

        // Function to get the canvas's position
    function getCanvasPosition(canvas) {
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        return {
            left: rect.left + window.scrollX,
            top: rect.top + window.scrollY
        };
    }

    // Function to handle the mouse move event
    function handleMouseMove(event) {
        const canvasPos = getCanvasPosition(canvas);
        const mouseX = event.clientX - canvasPos.left;
        const mouseY = event.clientY - canvasPos.top;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.beginPath();
        ctx.arc(mouseX, mouseY, 50, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255, 0.1)';
        ctx.fill();
        ctx.closePath();

    }

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseleave', function(){
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    });
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
                lastClosest.classList.remove('bg-[linear-gradient(0deg,#d6fcff,#fff_90%)]');
                lastClosest.classList.remove('dark:bg-[linear-gradient(0deg,#6acbe182,#000_90%)]');
            }
            if(closest !== null){
                closest.classList.add('scale-105');
                closest.classList.add('bg-[linear-gradient(0deg,#d6fcff,#fff_90%)]');
                closest.classList.add('dark:bg-[linear-gradient(0deg,#6acbe182,#000_90%)]');
            }
            lastClosest = closest;
        }
    }

    function closeDragElement() {
        // Beenden des Ziehens
        document.onmouseup = null;
        document.onmousemove = null;
        if (Math.abs(startx) < 10 && Math.abs(starty) < 10){
            console.log("close enough")
            removeItem(item);
            // Wenn das Item nicht bewegt wurde, dann wird ein neues in der Mitte des Canvas (+-20% höhe & breite) erstellt
            canvas = document.getElementById('canvas');
            new_x = canvas.offsetWidth / 2 + (Math.random() - 0.5) * canvas.offsetWidth * 0.2;
            new_y = canvas.offsetHeight / 2 + (Math.random() - 0.5) * canvas.offsetHeight * 0.2;
            createItem(item.emoji, item.name, new_x,new_y, undefined, true);
            return;
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

