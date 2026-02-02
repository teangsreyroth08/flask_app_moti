🎀 Moti: Today's Cute Motivation
Moti is a minimalist, aesthetic web application designed to brighten your day with a single quote. Whether you need a push to keep coding or just a little spark of joy, Moti is here to help you "start where you are."✨

<img width="1906" height="910" alt="image" src="https://github.com/user-attachments/assets/8212f9f5-0f0d-4996-a3ef-f4fab30fab34" />

/* 1. The "Entrance" - Makes the whole app float up on load */
@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(30px) scale(0.98);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

.main-container {
    animation: fadeInUp 0.8s cubic-bezier(0.22, 1, 0.36, 1);
}

/* 2. The "Bouncy" Buttons - Feel like pressing a soft marshmallow */
.button-primary, .button-secondary {
    transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.button-primary:hover, .button-secondary:hover {
    transform: scale(1.05); /* Slight grow */
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
}

.button-primary:active, .button-secondary:active {
    transform: scale(0.95); /* Slight squish when clicked */
}

/* 3. The Quote Fade - For when you fetch a "New Quote" via Flask/JS */
.quote-text {
    transition: opacity 0.4s ease-in-out;
}

.fade-out {
    opacity: 0;
}

/* 4. The "Floating" Character - A subtle hover effect for the mascot */
@keyframes softFloat {
    0% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
    100% { transform: translateY(0); }
}

.mascot-image {
    animation: softFloat 4s ease-in-out infinite;
}

/* 5. Input Glow - When the user focuses on the "Add your own" box */
input, textarea {
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

input:focus, textarea:focus {
    outline: none;
    border-color: #ffb7c5;
    box-shadow: 0 0 8px rgba(255, 183, 197, 0.5);
}
