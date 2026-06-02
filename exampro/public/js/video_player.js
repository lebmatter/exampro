/**
 * Framework-agnostic chunked-video player used by the proctor dashboard and
 * the Exam Submission desk doctype view. Operates on a single `<video>`
 * element plus an optional set of control buttons and an index display.
 *
 * Usage:
 *   const player = new VideoPlayer({
 *       videoEl: '#my-video',
 *       prevBtn: '#prev', nextBtn: '#next',
 *       playPauseBtn: '#play-pause',
 *       indexField: '#index-field',
 *   });
 *   player.loadChunks([url1, url2, ...]);  // sorted oldest-first
 *
 * Any control option may be omitted; the corresponding button simply has no
 * wired behaviour. `videoEl` is the only required option.
 */
(function (root) {
    function resolve(el) {
        if (!el) return null;
        if (typeof el === 'string') return document.querySelector(el);
        return el;
    }

    function attach(el, handler) {
        if (!el || !handler) return;
        el.addEventListener('click', handler);
    }

    function handlePlayError(error) {
        if (error && error.name === 'AbortError') {
            console.log('Video play aborted (normal when switching chunks quickly)');
        } else if (error && error.name === 'NotAllowedError') {
            console.log('Video autoplay not allowed; user interaction required');
        } else if (error) {
            console.error('Error playing video:', error);
        }
    }

    function VideoPlayer(opts) {
        this.videoEl = resolve(opts.videoEl);
        if (!this.videoEl) {
            throw new Error('VideoPlayer: videoEl is required');
        }
        this.prevBtn = resolve(opts.prevBtn);
        this.nextBtn = resolve(opts.nextBtn);
        this.playPauseBtn = resolve(opts.playPauseBtn);
        this.skipBackBtn = resolve(opts.skipBackBtn);
        this.skipForwardBtn = resolve(opts.skipForwardBtn);
        this.goLiveBtn = resolve(opts.goLiveBtn);
        this.indexField = resolve(opts.indexField);
        this.onChange = opts.onChange || null;

        this.chunks = [];
        this.currentIndex = 0;

        this._onEnded = () => this.next();
        this.videoEl.addEventListener('ended', this._onEnded);

        attach(this.prevBtn, () => this.prev());
        attach(this.nextBtn, () => this.next());
        attach(this.playPauseBtn, () => this.togglePlay());
        attach(this.skipBackBtn, () => this.seekRelative(-10));
        attach(this.skipForwardBtn, () => this.seekRelative(10));
        attach(this.goLiveBtn, () => this.goLive());

        this._updateIndexField();
    }

    // Update the chunk list without changing playback. Clamps currentIndex so
    // the caller doesn't have to. Use this for poll-driven updates.
    VideoPlayer.prototype.setChunks = function (chunks) {
        this.chunks = Array.isArray(chunks) ? chunks.slice() : [];
        if (this.chunks.length === 0) {
            this.currentIndex = 0;
            this.videoEl.removeAttribute('src');
            this.videoEl.load();
        } else if (this.currentIndex >= this.chunks.length) {
            this.currentIndex = this.chunks.length - 1;
        }
        this._updateIndexField();
    };

    // Convenience: set the chunk list and start playback from the first chunk.
    VideoPlayer.prototype.loadChunks = function (chunks) {
        this.setChunks(chunks);
        if (this.chunks.length > 0) {
            this.playAt(0);
        }
    };

    VideoPlayer.prototype.playAt = function (index) {
        if (index < 0 || index >= this.chunks.length) return;
        this.currentIndex = index;
        const newSrc = this.chunks[index];
        if (this.videoEl.src !== newSrc) {
            this.videoEl.pause();
            this.videoEl.src = newSrc;
            this.videoEl.load();
        }
        this.videoEl.play().catch(handlePlayError);
        this._updateIndexField();
        if (this.onChange) this.onChange(index, this.chunks.length);
    };

    VideoPlayer.prototype.next = function () {
        if (this.currentIndex + 1 < this.chunks.length) {
            this.playAt(this.currentIndex + 1);
        }
    };

    VideoPlayer.prototype.prev = function () {
        if (this.currentIndex > 0) {
            this.playAt(this.currentIndex - 1);
        }
    };

    VideoPlayer.prototype.togglePlay = function () {
        if (!this.chunks.length) return;
        if (this.videoEl.paused || this.videoEl.ended) {
            this.videoEl.play().catch(handlePlayError);
        } else {
            this.videoEl.pause();
        }
    };

    VideoPlayer.prototype.seekRelative = function (seconds) {
        // Seek within the current chunk; crossing chunk boundaries is handled
        // by next/prev because each chunk is an independent file.
        if (!isFinite(this.videoEl.duration)) return;
        const target = (this.videoEl.currentTime || 0) + seconds;
        this.videoEl.currentTime = Math.max(0, Math.min(target, this.videoEl.duration));
    };

    VideoPlayer.prototype.goLive = function () {
        if (this.chunks.length > 0) {
            this.playAt(this.chunks.length - 1);
        }
    };

    VideoPlayer.prototype._updateIndexField = function () {
        if (!this.indexField) return;
        const total = this.chunks.length;
        const shown = total === 0 ? 0 : (this.currentIndex + 1);
        const text = `${shown}/${total}`;
        if ('value' in this.indexField) {
            this.indexField.value = text;
        } else {
            this.indexField.textContent = text;
        }
    };

    VideoPlayer.prototype.destroy = function () {
        this.videoEl.removeEventListener('ended', this._onEnded);
        this.videoEl.pause();
        this.videoEl.removeAttribute('src');
        this.videoEl.load();
    };

    root.VideoPlayer = VideoPlayer;
})(typeof window !== 'undefined' ? window : this);
