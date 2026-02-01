// static/js/app.js
// ===== CONFIGURATION =====
const API_BASE_URL = window.location.origin; // Same origin as the frontend
const REFRESH_INTERVAL = 30000; // 30 seconds

// DOM Elements
const postsContainer = document.getElementById('postsContainer');
const tagSelect = document.getElementById('tagSelect');
const refreshBtn = document.getElementById('refreshBtn');
const loadingEl = document.getElementById('loading');
const noPostsEl = document.getElementById('noPosts');
const countdownEl = document.getElementById('countdown');
const totalPostsEl = document.getElementById('totalPosts');
const activeTagsEl = document.getElementById('activeTags');
const todayPostsEl = document.getElementById('todayPosts');
const lastUpdateEl = document.getElementById('lastUpdate');
const searchInput = document.getElementById('searchInput');
const tagCloudEl = document.getElementById('tagCloud');

// State
let allPosts = [];
let allTags = new Set();
let countdown = REFRESH_INTERVAL / 1000;
let refreshTimer;
let countdownTimer;

// ===== FUNCTIONS =====

// Format date nicely
function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
            return 'Recently';
        }
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return 'Recently';
    }
}

// Update dashboard stats
function updateDashboardStats(posts) {
    totalPostsEl.textContent = posts.length;
    
    // Count unique tags
    const tags = new Set();
    posts.forEach(post => {
        if (post.tags) {
            post.tags.split(',').forEach(tag => {
                if (tag.trim()) tags.add(tag.trim());
            });
        }
    });
    activeTagsEl.textContent = tags.size;
    
    // Count today's posts
    const today = new Date().toDateString();
    const todayCount = posts.filter(post => {
        try {
            const postDate = new Date(post.created_at).toDateString();
            return postDate === today;
        } catch (e) {
            return false;
        }
    }).length;
    todayPostsEl.textContent = todayCount;
    
    // Update tag cloud
    updateTagCloud(Array.from(tags));
}

// Create tag cloud
function updateTagCloud(tags) {
    if (tags.length === 0) {
        tagCloudEl.innerHTML = '<p>No tags yet</p>';
        return;
    }
    
    let html = '';
    tags.slice(0, 8).forEach(tag => {
        const randomSize = Math.floor(Math.random() * 6) + 14;
        const randomColor = `hsl(${Math.random() * 360}, 70%, 60%)`;
        html += `<span class="tag-cloud-item" style="font-size: ${randomSize}px; color: ${randomColor};" data-tag="${tag}">${tag}</span> `;
    });
    tagCloudEl.innerHTML = html;
    
    // Add click event to tag cloud items
    document.querySelectorAll('.tag-cloud-item').forEach(item => {
        item.addEventListener('click', () => {
            tagSelect.value = item.dataset.tag;
            filterPosts();
        });
    });
}

// Fetch posts from backend API
async function fetchPosts() {
    try {
        loadingEl.style.display = 'block';
        noPostsEl.style.display = 'none';
        
        const response = await fetch(`${API_BASE_URL}/api/posts`);
        if (!response.ok) {
            if (response.status === 404) {
                // Try channel posts endpoint as fallback
                const channelResponse = await fetch(`${API_BASE_URL}/api/channel/posts`);
                if (channelResponse.ok) {
                    const channelData = await channelResponse.json();
                    allPosts = channelData.data?.posts || [];
                } else {
                    throw new Error(`API error: ${response.status}`);
                }
            } else {
                throw new Error(`API error: ${response.status}`);
            }
        } else {
            const data = await response.json();
            allPosts = data.posts || [];
        }
        
        // Update dashboard
        updateDashboardStats(allPosts);
        
        // Extract tags for filter dropdown
        extractTags();
        populateTagFilter();
        
        // Display posts
        displayPosts(allPosts);
        
        // Update last update time
        lastUpdateEl.textContent = 'Just now';
        loadingEl.style.display = 'none';
        
        if (allPosts.length === 0) {
            noPostsEl.style.display = 'block';
        }
        
    } catch (error) {
        console.error('Error fetching posts:', error);
        loadingEl.style.display = 'none';
        postsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <h3>Connection Error</h3>
                <p>Unable to connect to the 4UTODAY backend.</p>
                <p>Error: ${error.message}</p>
                <button class="refresh-btn" onclick="fetchPosts()" style="margin-top: 20px;">
                    <i class="fas fa-sync-alt"></i> Retry
                </button>
            </div>
        `;
    }
}

// Extract unique tags from posts
function extractTags() {
    allTags.clear();
    allPosts.forEach(post => {
        if (post.tags) {
            post.tags.split(',').forEach(tag => {
                const cleanTag = tag.trim();
                if (cleanTag) allTags.add(cleanTag);
            });
        }
    });
}

// Populate tag filter dropdown
function populateTagFilter() {
    const currentTag = tagSelect.value;
    
    // Keep "All Posts" option
    tagSelect.innerHTML = '<option value="all">All Posts</option>';
    
    // Add sorted tags
    const sortedTags = Array.from(allTags).sort();
    sortedTags.forEach(tag => {
        const option = document.createElement('option');
        option.value = tag;
        option.textContent = tag;
        tagSelect.appendChild(option);
    });
    
    // Restore selection
    if (currentTag && Array.from(allTags).includes(currentTag)) {
        tagSelect.value = currentTag;
    }
}

// Display posts in grid
function displayPosts(posts) {
    postsContainer.innerHTML = '';
    
    if (posts.length === 0) {
        noPostsEl.style.display = 'block';
        return;
    }
    
    noPostsEl.style.display = 'none';
    
    posts.forEach(post => {
        const card = document.createElement('article');
        card.className = 'post-card';
        
        // Determine media type and create HTML
        let mediaHtml = '';
        if (post.file_url) {
            const isVideo = post.file_url.match(/\.(mp4|webm|ogg|mov)$/i) || 
                           post.file_url.includes('youtube.com') || 
                           post.file_url.includes('youtu.be');
            
            if (isVideo) {
                mediaHtml = `
                    <div class="no-media">
                        <i class="fas fa-video"></i>
                    </div>
                `;
            } else {
                mediaHtml = `<img src="${post.file_url}" alt="${post.post_title || 'Post image'}" class="post-media" loading="lazy" onerror="this.style.display='none'; this.parentNode.querySelector('.no-media')?.style.display='flex';">`;
                // Add fallback
                mediaHtml += `<div class="no-media" style="display: none;">
                    <i class="fas fa-image"></i>
                </div>`;
            }
        } else {
            mediaHtml = `
                <div class="no-media">
                    <i class="fas fa-paperclip"></i>
                </div>
            `;
        }
        
        // Create tags HTML
        let tagsHtml = '';
        if (post.tags && post.tags !== 'telegram') {
            tagsHtml = post.tags.split(',').map(tag => {
                const cleanTag = tag.trim();
                if (!cleanTag) return '';
                return `<span class="tag" data-tag="${cleanTag}">${cleanTag}</span>`;
            }).join('');
        }
        
        // Format date
        const formattedDate = formatDate(post.created_at);
        
        card.innerHTML = `
            ${mediaHtml}
            <div class="post-content">
                <h3 class="post-title">${escapeHtml(post.post_title || 'Untitled Post')}</h3>
                <div class="post-meta">
                    <span><i class="far fa-clock"></i> ${formattedDate}</span>
                    <span><i class="far fa-comment"></i> #${post.telegram_message_id || post.id}</span>
                </div>
                <p class="post-description">${escapeHtml(post.post_description || post.content || 'No description available')}</p>
                ${tagsHtml ? `<div class="post-tags">${tagsHtml}</div>` : ''}
                <div class="post-actions">
                    ${post.file_url ? `<a href="${post.file_url}" target="_blank" class="action-btn view-btn"><i class="fas fa-external-link-alt"></i> View File</a>` : ''}
                    <button class="action-btn save-btn" onclick="savePost(${post.id})">
                        <i class="far fa-bookmark"></i> Save
                    </button>
                </div>
            </div>
        `;
        
        postsContainer.appendChild(card);
    });
    
    // Add click event to tags
    document.querySelectorAll('.post-tags .tag').forEach(tag => {
        tag.addEventListener('click', (e) => {
            tagSelect.value = e.target.dataset.tag;
            filterPosts();
        });
    });
}

// Filter posts based on selected tag
function filterPosts() {
    const selectedTag = tagSelect.value;
    if (selectedTag === 'all') {
        displayPosts(allPosts);
    } else {
        const filtered = allPosts.filter(post => 
            post.tags && post.tags.toLowerCase().includes(selectedTag.toLowerCase())
        );
        displayPosts(filtered);
    }
}

// Search posts
function searchPosts() {
    const searchTerm = searchInput.value.toLowerCase();
    if (!searchTerm) {
        displayPosts(allPosts);
        return;
    }
    
    const filtered = allPosts.filter(post => 
        (post.post_title && post.post_title.toLowerCase().includes(searchTerm)) ||
        (post.post_description && post.post_description.toLowerCase().includes(searchTerm)) ||
        (post.content && post.content.toLowerCase().includes(searchTerm)) ||
        (post.tags && post.tags.toLowerCase().includes(searchTerm))
    );
    
    displayPosts(filtered);
}

// Save post (example function)
function savePost(postId) {
    alert(`Post #${postId} saved to your favorites!`);
    // In a real app, you would save this to localStorage or send to backend
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Countdown timer for auto-refresh
function updateCountdown() {
    countdown--;
    countdownEl.textContent = countdown;
    if (countdown <= 0) {
        countdown = REFRESH_INTERVAL / 1000;
        fetchPosts();
    }
}

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch
    fetchPosts();
    
    // Set up auto-refresh
    refreshTimer = setInterval(fetchPosts, REFRESH_INTERVAL);
    countdownTimer = setInterval(updateCountdown, 1000);
    
    // Event listeners
    tagSelect.addEventListener('change', filterPosts);
    refreshBtn.addEventListener('click', () => {
        countdown = REFRESH_INTERVAL / 1000;
        countdownEl.textContent = countdown;
        fetchPosts();
    });
    
    searchInput.addEventListener('input', searchPosts);
    
    // Also fetch stats from /api/stats endpoint
    fetch(`${API_BASE_URL}/api/stats`)
        .then(res => {
            if (res.ok) return res.json();
            return fetch(`${API_BASE_URL}/api/channel/stats`);
        })
        .then(res => res.json())
        .then(stats => {
            // Update stats if needed
            if (stats.data) {
                totalPostsEl.textContent = stats.data.total_posts || stats.total_posts || 0;
            }
        })
        .catch(console.error);
});

// Clean up timers when page is hidden
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        clearInterval(refreshTimer);
        clearInterval(countdownTimer);
    } else {
        refreshTimer = setInterval(fetchPosts, REFRESH_INTERVAL);
        countdownTimer = setInterval(updateCountdown, 1000);
    }
});
