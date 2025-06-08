
var shouldSend = true;

recv("config", function (message) {
    send("Pointer Recieved: " + ptr(message.payload));
    var targetAddr = ptr(message.payload);
    try {
        Interceptor.attach((targetAddr), {
            onEnter: function (args) {
                if (shouldSend) {
                    send("onEnter");
                }

                var base = this.context.r13;
                var index = this.context.r8;
    
                var memAddr = base.add(index);
                
                if (shouldSend) {
                    send("T:" + memAddr);
                }
            }
        })
    } catch(e) {
        send("Interceptor failed" + e)
    }

}).then(

);


