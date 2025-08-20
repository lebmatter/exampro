// Simple JS Confetti implementation
class JSConfetti {
    constructor() {
        this.canvas = document.createElement('canvas');
        this.context = this.canvas.getContext('2d');
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.canvas.style.position = 'fixed';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.zIndex = '1000';
        this.canvas.style.pointerEvents = 'none';
        document.body.appendChild(this.canvas);
        
        this.particles = [];
        this.colors = ['#ffd700', '#ff6b6b', '#4ecdc4', '#7c3aed', '#f59e0b', '#10b981'];
    }
    
    addParticle(x, y) {
        this.particles.push({
            x,
            y,
            color: this.colors[Math.floor(Math.random() * this.colors.length)],
            size: Math.random() * 10 + 5,
            speedX: Math.random() * 6 - 3,
            speedY: Math.random() * -7 - 2,
            gravity: 0.1,
            rotation: Math.random() * 360,
            rotationSpeed: Math.random() * 10 - 5
        });
    }
    
    update() {
        this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        for (let i = 0; i < this.particles.length; i++) {
            const p = this.particles[i];
            
            // Update position
            p.x += p.speedX;
            p.y += p.speedY;
            p.speedY += p.gravity;
            p.rotation += p.rotationSpeed;
            
            // Draw particle
            this.context.save();
            this.context.translate(p.x, p.y);
            this.context.rotate(p.rotation * Math.PI / 180);
            this.context.fillStyle = p.color;
            this.context.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
            this.context.restore();
            
            // Remove particles that are out of the screen
            if (p.y > this.canvas.height) {
                this.particles.splice(i, 1);
                i--;
            }
        }
        
        if (this.particles.length > 0) {
            requestAnimationFrame(() => this.update());
        } else {
            // Remove canvas when all particles are gone
            this.canvas.remove();
        }
    }
    
    addConfetti(x, y, amount = 100) {
        for (let i = 0; i < amount; i++) {
            this.addParticle(x, y);
        }
        this.update();
    }
}

// Generate background confetti
function generateBackgroundConfetti() {
    const confettiBg = document.getElementById('confetti-bg');
    const shapes = ['circle', 'square', 'diamond', 'star'];
    const colors = ['#ffd700', '#ff6b6b', '#4ecdc4', '#7c3aed', '#f59e0b', '#10b981', '#f97316', '#ec4899'];
    const confettiCount = 10;
    
    // Clear existing confetti
    confettiBg.innerHTML = '';
    
    for (let i = 0; i < confettiCount; i++) {
        const confetti = document.createElement('div');
        const shape = shapes[Math.floor(Math.random() * shapes.length)];
        const color = colors[Math.floor(Math.random() * colors.length)];
        const size = Math.random() * 12 + 8; // 8-20px
        
        confetti.className = `confetti-piece confetti-${shape}`;
        confetti.style.left = Math.random() * 100 + '%';
        confetti.style.top = Math.random() * 100 + '%';
        confetti.style.animationDelay = Math.random() * 6 + 's';
        confetti.style.animationDuration = (Math.random() * 4 + 4) + 's'; // 4-8s
        
        if (shape === 'triangle') {
            confetti.style.borderLeft = `${size/2}px solid transparent`;
            confetti.style.borderRight = `${size/2}px solid transparent`;
            confetti.style.borderBottom = `${size}px solid ${color}`;
        } else {
            confetti.style.width = size + 'px';
            confetti.style.height = size + 'px';
            confetti.style.backgroundColor = color;
        }
        
        confettiBg.appendChild(confetti);
    }
}

// Initialize Easter egg and background confetti
document.addEventListener('DOMContentLoaded', function() {
    // Generate background confetti on page load
    generateBackgroundConfetti();
    
    // Get the first ranked participant (if exists)
    const firstRankNameElement = document.querySelector('.rank-1-name');
    
    if (firstRankNameElement) {
        // Add a click event listener to just the name element
        firstRankNameElement.addEventListener('click', function(e) {
            // Create confetti instance and trigger effect
            const confetti = new JSConfetti();
            const rect = firstRankNameElement.getBoundingClientRect();
            confetti.addConfetti(e.clientX || rect.left + rect.width/2, e.clientY || rect.top, 150);
            
            // Add a little animation to the name element
            firstRankNameElement.style.transition = 'transform 0.3s ease';
            firstRankNameElement.style.transform = 'scale(1.05)';
            setTimeout(() => {
                firstRankNameElement.style.transform = '';
            }, 300);
        });
        
        // Add cursor pointer to indicate clickability
        firstRankNameElement.style.cursor = 'pointer';
        firstRankNameElement.setAttribute('title', 'Click for a surprise!');
    }
});