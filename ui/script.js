waiting_pairs = {};
last_pair_id = 1;
let socket = null;

function handleBingoClick(payload){
    if(socket && socket.connected){
        socket.emit('bingo_click', payload);
    }
}

function getServerUrl() {
    const raw = (window.environment && window.environment.SERVER_HOST) || window.location.origin;
    if (raw.startsWith('http://') || raw.startsWith('https://')) {
        return raw;
    }
    const protocol = window.location.protocol === 'https:' ? 'https' : 'http';
    return `${protocol}://${raw}`;
}

function getPair(item1, item2){
    if(socket !== null && socket.connected){
        const id = last_pair_id++;
        socket.emit('pair', {pair: [item1.name, item2.name], id});
        waiting_pairs[id] = [item1, item2];
        return true;
    }
    return false;
}

function parseServerData(data){ 
    //check if data has field type
    if(data.type === undefined){
        return;
    }
    switch(data.type){
        case "pair_result":
            if(data.data === undefined){
                return;
            }
            if(data.data.id === undefined){
                return;
            }
            if(data.data.id in waiting_pairs){
                let item1 = waiting_pairs[data.data.id][0];
                let item2 = waiting_pairs[data.data.id][1];
                waiting_pairs[data.data.id] = undefined;
                if(data.data.new_item !== undefined && data.data.new_item != null){
                    if(data.data.new_item.emoji !== undefined&&data.data.new_item.name !== undefined){
                    console.log("pair result with new item");
                    createItem(data.data.new_item.emoji,data.data.new_item.name,(item1.offsetLeft+item2.offsetLeft)/2,(item1.offsetTop+item2.offsetTop)/2,undefined,false);
                    item1.remove();
                    item2.remove();
                    }
                }else{
                    console.log("pair result without new item");
                    item1.pairing = false;
                    item2.pairing = false;
                    item1.classList.remove('opacity-50');
                    item2.classList.remove('opacity-50');
                }
            }
            break;
        case "mode":
            if(data.data !== undefined){
                setStatus(data.data);
            }
            break;
        case "username":
            if(data.data !== undefined){
                setUsername("Du bist: "+data.data);
            }
            break;
        case "clear":
            clearItems();
            break;
        case "items":
            if(data.data !== undefined){
                for(let key in item_buttons){
                    if(!data.data.some(item => item.name === key)){
                        item_buttons[key].remove();
                        delete item_buttons[key];
                    }
                }
                for(let item of data.data){
                    if(item.emoji !== undefined&&item.name !== undefined){
                        createItemButton(item.emoji,item.name);
                    }else{
                        console.log("item without emoji or name",item);
                    }
                }
            }
            break;
        case "bingo":
            setBingoField(data.data);
            break;
        case "news":
            if(data.data !== undefined){
                setNews(data.data);
            }
            break;
        case "error":
            console.log("error");
            if(data.data){
                alert(data.data);
            }
            break;
        case "retry":
            location.reload();
            break;
        default:
            console.log("unknown message type: "+data.type);
            break;
    }

}

function updateUsername(){
    let username = localStorage.getItem('username');
    if (username) {
        socket?.emit('username', {name: username});
    }
}

function setConnStatus(status){
    const connNotConnected = document.getElementById('conn-notconnected');
    const connConnecting = document.getElementById('conn-connecting');
    const connConnected = document.getElementById('conn-connected');
    const connDisconnected = document.getElementById('conn-disconnected');

    connNotConnected.classList.toggle('hidden', status !== 0);
    connConnecting.classList.toggle('hidden', status !== 1);
    connConnected.classList.toggle('hidden', status !== 2);
    connDisconnected.classList.toggle('hidden', status !== 3);
}

function connectToServer(name){
    console.log("connecting to server");
    setConnStatus(1);

    const serverUrl = getServerUrl();
    socket = io(`${serverUrl}/game`, {
        path: '/socket.io',
        transports: ['websocket'],
        reconnectionAttempts: 10,
        reconnectionDelayMax: 3000,
    });

    socket.on('connect', () => {
        setConnStatus(2);
        socket.emit('join', {});
    });

    socket.on('server_message', (payload) => {
        try {
            parseServerData(payload);
        } catch (error) {
            console.log('Could not parse payload', error);
        }
    });

    socket.on('disconnect', () => {
        setConnStatus(3);
    });

    socket.on('connect_error', () => {
        setConnStatus(3);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOMContentLoaded event");
    initClient(getPair, () => {}, handleBingoClick);
})

window.addEventListener('load', function() {
    console.log("load event");
    connectToServer();
})
