
var shouldSend = true;

recv("config", function (message) {
    send("Pointer Recieved: " + ptr(message.payload));
    var targetAddr = ptr(message.payload);
    try {
        Interceptor.attach((targetAddr), {
            onEnter: function (args) {
                var base = this.context.r13;
                var index = this.context.r12;
    
                var memAddr = base.add(index);
                if (shouldSend) {
                    send("M:" + memAddr);
                    shouldSend = false;
                }

            }
        })
    } catch(e) {
        send("Interceptor failed")
    }


}).then(

);

