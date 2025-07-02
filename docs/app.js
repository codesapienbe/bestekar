// DOM Elements
const durationSlider = document.getElementById('duration');
const durationValue = document.getElementById('duration-value');
const generateBtn = document.getElementById('generate-btn');
const btnText = generateBtn.querySelector('.btn__text');
const btnLoading = generateBtn.querySelector('.btn__loading');
const musicPlayer = document.getElementById('music-player');
const playBtn = document.getElementById('play-btn');
const progressFill = document.getElementById('progress-fill');
const totalTimeSpan = document.getElementById('total-time');
const lyricsTextarea = document.getElementById('lyrics');
const styleSelect = document.getElementById('style');
const waveform = document.getElementById('waveform');

// Sample lyrics for different styles
const sampleLyrics = {
    'Turkish emotional ballad, acoustic guitar, soft piano': `Gece iner, başın yastıkta ağır,
Düşünceler döner, kalbinde bir çağrı.
Uyku kaçar, gözlerin dalar,
Endişe sarar, ruhunu yorar.`,
    
    'Turkish folk song, traditional instruments, emotional vocals': `Dağlar yüksek, yollar taşlı,
Gurbet elde gönül yaşlı.
Anadolu'nun türküsü,
Yüreğimde yankısı.`,
    
    'Turkish pop ballad, contemporary, heartfelt vocals': `Şehrin ışıkları yanıyor,
Gecenin sessizliğinde.
Hayallerim uçuyor,
Müziğin ritmiyle.`,
    
    'Turkish acoustic song, guitar, intimate, emotional': `Gitar telleri titriyor,
Sessizlikte yankılanıyor.
Kalbimin şarkısı,
Sevdanın melodisi.`,
    
    'Turkish romantic ballad, soft melody, love song': `Sevda gelir, kalbe sığmaz,
Gözlerin güneş, her şey aydınlanır.
Ellerim titrer, sözler bulanır,
Aşkın rüzgarı, içimi kanatır.`
};

// State management
let isPlaying = false;
let currentProgress = 0;
let progressInterval = null;
let currentDuration = 30;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeDurationSlider();
    initializeNavigation();
    initializeGenerateButton();
    initializePlayButton();
    initializeSamplePlayers();
    initializeStyleSelector();
    initializeWaveformAnimation();
});

// Duration slider functionality
function initializeDurationSlider() {
    durationSlider.addEventListener('input', function() {
        currentDuration = parseInt(this.value);
        durationValue.textContent = currentDuration;
        updateTotalTime();
    });
}

// Navigation smooth scrolling
function initializeNavigation() {
    const navLinks = document.querySelectorAll('.nav__link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            
            if (targetSection) {
                const headerHeight = 80;
                const targetPosition = targetSection.offsetTop - headerHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// Generate button functionality
function initializeGenerateButton() {
    generateBtn.addEventListener('click', function() {
        if (this.classList.contains('loading')) return;
        
        generateMusic();
    });
}

// Music generation simulation
function generateMusic() {
    // Start loading state
    generateBtn.classList.add('loading');
    btnText.classList.add('hidden');
    btnLoading.classList.remove('hidden');
    btnLoading.classList.add('active');
    
    // Start waveform animation
    startWaveformAnimation();
    
    // Simulate generation process
    setTimeout(() => {
        // Stop loading state
        generateBtn.classList.remove('loading');
        btnText.classList.remove('hidden');
        btnLoading.classList.add('hidden');
        btnLoading.classList.remove('active');
        
        // Show music player
        musicPlayer.classList.remove('hidden');
        musicPlayer.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Stop waveform animation
        stopWaveformAnimation();
        
        // Reset player state
        resetPlayer();
        
    }, 3000); // 3 second simulation
}

// Waveform animation
function startWaveformAnimation() {
    const bars = waveform.querySelectorAll('.waveform__bar');
    bars.forEach(bar => {
        bar.style.animationPlayState = 'running';
    });
}

function stopWaveformAnimation() {
    const bars = waveform.querySelectorAll('.waveform__bar');
    bars.forEach(bar => {
        bar.style.animationPlayState = 'paused';
    });
}

function initializeWaveformAnimation() {
    const bars = waveform.querySelectorAll('.waveform__bar');
    bars.forEach(bar => {
        bar.style.animationPlayState = 'paused';
    });
}

// Play button functionality
function initializePlayButton() {
    playBtn.addEventListener('click', function() {
        if (isPlaying) {
            pauseMusic();
        } else {
            playMusic();
        }
    });
}

// Music player controls
function playMusic() {
    isPlaying = true;
    playBtn.textContent = '⏸️';
    startWaveformAnimation();
    
    // Start progress animation
    progressInterval = setInterval(() => {
        currentProgress += (100 / currentDuration) / 10; // Update every 100ms
        
        if (currentProgress >= 100) {
            currentProgress = 100;
            pauseMusic();
        }
        
        progressFill.style.width = currentProgress + '%';
        updateCurrentTime();
    }, 100);
}

function pauseMusic() {
    isPlaying = false;
    playBtn.textContent = '▶️';
    stopWaveformAnimation();
    
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

function resetPlayer() {
    pauseMusic();
    currentProgress = 0;
    progressFill.style.width = '0%';
    updateCurrentTime();
}

// Time display functions
function updateTotalTime() {
    const minutes = Math.floor(currentDuration / 60);
    const seconds = currentDuration % 60;
    totalTimeSpan.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function updateCurrentTime() {
    const currentSeconds = Math.floor((currentProgress / 100) * currentDuration);
    const minutes = Math.floor(currentSeconds / 60);
    const seconds = currentSeconds % 60;
    const currentTimeSpan = document.querySelector('.progress__time');
    const totalTime = totalTimeSpan.textContent;
    currentTimeSpan.innerHTML = `${minutes}:${seconds.toString().padStart(2, '0')} / ${totalTime}`;
}

// Sample players functionality
function initializeSamplePlayers() {
    const samplePlayBtns = document.querySelectorAll('.sample-play-btn');
    
    samplePlayBtns.forEach((btn, index) => {
        btn.addEventListener('click', function() {
            // Stop all other sample players
            samplePlayBtns.forEach(otherBtn => {
                if (otherBtn !== btn) {
                    otherBtn.textContent = '▶️';
                    otherBtn.classList.remove('playing');
                }
            });
            
            // Toggle current player
            if (this.classList.contains('playing')) {
                this.textContent = '▶️';
                this.classList.remove('playing');
            } else {
                this.textContent = '⏸️';
                this.classList.add('playing');
                
                // Simulate playing for a few seconds then stop
                setTimeout(() => {
                    this.textContent = '▶️';
                    this.classList.remove('playing');
                }, 3000);
            }
        });
    });
}

// Style selector functionality
function initializeStyleSelector() {
    styleSelect.addEventListener('change', function() {
        const selectedStyle = this.value;
        if (sampleLyrics[selectedStyle]) {
            lyricsTextarea.value = sampleLyrics[selectedStyle];
        }
    });
}

// Progress bar click functionality
function initializeProgressBar() {
    const progressBar = document.querySelector('.progress__bar');
    
    if (progressBar) {
        progressBar.addEventListener('click', function(e) {
            const rect = this.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const percentage = (clickX / rect.width) * 100;
            
            currentProgress = Math.max(0, Math.min(100, percentage));
            progressFill.style.width = currentProgress + '%';
            updateCurrentTime();
        });
    }
}

// Scroll animations
function initializeScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // Observe feature cards and other elements
    const animatedElements = document.querySelectorAll('.feature-card, .sample-card, .step');
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// Keyboard shortcuts
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Space bar to play/pause
        if (e.code === 'Space' && !musicPlayer.classList.contains('hidden')) {
            e.preventDefault();
            playBtn.click();
        }
        
        // Enter to generate music
        if (e.code === 'Enter' && (e.target === lyricsTextarea || e.target === styleSelect)) {
            e.preventDefault();
            generateBtn.click();
        }
    });
}

// Touch/swipe support for mobile
function initializeTouchSupport() {
    let touchStartX = 0;
    let touchEndX = 0;
    
    const progressBar = document.querySelector('.progress__bar');
    
    if (progressBar) {
        progressBar.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
        });
        
        progressBar.addEventListener('touchend', function(e) {
            touchEndX = e.changedTouches[0].clientX;
            const rect = this.getBoundingClientRect();
            const touchX = touchEndX - rect.left;
            const percentage = (touchX / rect.width) * 100;
            
            currentProgress = Math.max(0, Math.min(100, percentage));
            progressFill.style.width = currentProgress + '%';
            updateCurrentTime();
        });
    }
}

// Error handling
function handleError(error) {
    console.error('Bestekar Error:', error);
    
    // Reset loading states
    generateBtn.classList.remove('loading');
    btnText.classList.remove('hidden');
    btnLoading.classList.add('hidden');
    btnLoading.classList.remove('active');
    
    // Show error message
    const errorMessage = document.createElement('div');
    errorMessage.className = 'error-message';
    errorMessage.textContent = 'Bir hata oluştu. Lütfen tekrar deneyin.';
    errorMessage.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: var(--color-error);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(errorMessage);
    
    setTimeout(() => {
        errorMessage.remove();
    }, 5000);
}

// Animation for error message
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);

// Theme switching (bonus feature)
function initializeThemeToggle() {
    const themeToggle = document.createElement('button');
    themeToggle.innerHTML = '🌙';
    themeToggle.className = 'theme-toggle';
    themeToggle.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        border: none;
        background: var(--color-primary);
        color: white;
        font-size: 20px;
        cursor: pointer;
        z-index: 1000;
        transition: all 0.3s ease;
        box-shadow: var(--shadow-lg);
    `;
    
    themeToggle.addEventListener('click', function() {
        const currentTheme = document.documentElement.getAttribute('data-color-scheme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-color-scheme', newTheme);
        this.innerHTML = newTheme === 'dark' ? '☀️' : '🌙';
        
        // Save preference
        localStorage.setItem('bestekar-theme', newTheme);
    });
    
    // Load saved theme
    const savedTheme = localStorage.getItem('bestekar-theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-color-scheme', savedTheme);
        themeToggle.innerHTML = savedTheme === 'dark' ? '☀️' : '🌙';
    }
    
    document.body.appendChild(themeToggle);
}

// Performance monitoring
function initializePerformanceMonitoring() {
    // Monitor memory usage
    if (performance.memory) {
        console.log('Memory usage:', {
            used: Math.round(performance.memory.usedJSHeapSize / 1048576) + ' MB',
            total: Math.round(performance.memory.totalJSHeapSize / 1048576) + ' MB',
            limit: Math.round(performance.memory.jsHeapSizeLimit / 1048576) + ' MB'
        });
    }
    
    // Monitor timing
    window.addEventListener('load', function() {
        const loadTime = performance.now();
        console.log('Page loaded in:', Math.round(loadTime) + 'ms');
    });
}

// Initialize additional features
document.addEventListener('DOMContentLoaded', function() {
    initializeProgressBar();
    initializeScrollAnimations();
    initializeKeyboardShortcuts();
    initializeTouchSupport();
    initializeThemeToggle();
    initializePerformanceMonitoring();
    
    // Initialize total time display
    updateTotalTime();
});

// Export functions for testing (if needed)
window.BestkarApp = {
    generateMusic,
    playMusic,
    pauseMusic,
    resetPlayer,
    handleError
};

// Service worker registration (for offline support)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        // Note: Service worker file would need to be created separately
        // navigator.serviceWorker.register('/sw.js').then(function(registration) {
        //     console.log('SW registered: ', registration);
        // }).catch(function(registrationError) {
        //     console.log('SW registration failed: ', registrationError);
        // });
    });
}