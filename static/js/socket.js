function createSocket(namespace, sessionId) {
    window.socket = io.connect('http://' + location.hostname + ':' + location.port + namespace);
    window.socket.on('connect', function() {
        window.socket.on('refresh', function() {
            location.reload();
        });
    });

    if (sessionId)
        window.socket.emit('join', { id: sessionId });

}