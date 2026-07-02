// Chatbot functionality
document.addEventListener('DOMContentLoaded', function() {
    const chatbot = document.getElementById('chatbot');
    const toggle = document.getElementById('chatbot-toggle');
    const messages = document.getElementById('chat-messages');
    const input = document.getElementById('chat-input');
    const send = document.getElementById('chat-send');

    toggle.addEventListener('click', function() {
        chatbot.style.display = chatbot.style.display === 'none' ? 'block' : 'none';
    });

    send.addEventListener('click', function() {
        const message = input.value;
        if (message) {
            addMessage('You', message);
            input.value = '';
            // Send to backend or Gemini
            fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: message })
            })
            .then(response => response.json())
            .then(data => {
                addMessage('Bot', data.response);
            });
        }
    });

    function addMessage(sender, text) {
        const msg = document.createElement('div');
        msg.innerHTML = `<strong>${sender}:</strong> ${text}`;
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }
});
