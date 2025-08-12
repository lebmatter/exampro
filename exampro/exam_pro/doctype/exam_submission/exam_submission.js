// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Exam Submission", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("Exam Submission", {
    refresh(frm) {
        // Handle video display
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_video_list",
            args: {
                "exam_submission": frm.doc.name,
            },
            callback: function (r) {

                // Convert the object into an array of key-value pairs
                const videoArray = Object.entries(r.message.videos);
                if (videoArray != 0) {
                    $('#videoDiv').removeClass("hidden");
                    // Sort the array based on Unix timestamps in ascending order
                    videoArray.sort((a, b) => a[0] - b[0]);
                    var videoElement = document.getElementById("candidateVideo");
                    var playPauseBtn = document.getElementById('play-pause-btn');
                    var previousBtn = document.getElementById('previous-btn');
                    var nextBtn = document.getElementById('next-btn');
                    var indexField = document.getElementById('index-field');

                    var currentIndex = 0;

                    function playVideo() {
                        videoElement.src = videoArray[currentIndex][1];
                        videoElement.play();
                        indexField.value = (currentIndex + 1) + '/' + videoArray.length;
                    }

                    playPauseBtn.addEventListener('click', function () {
                        if (videoElement.paused) {
                            videoElement.play();
                        } else {
                            videoElement.pause();
                        }
                    });

                    previousBtn.addEventListener('click', function () {
                        currentIndex--;
                        playVideo();
                    });

                    nextBtn.addEventListener('click', function () {
                        currentIndex++;
                        playVideo();
                    });

                    // Initial video playback
                    playVideo();
                }
            },
        });

        // Replace retina_location_log field with canvas plot
        if (frm.doc.retina_location_log) {
            // Hide the original JSON field
            frm.set_df_property('retina_location_log', 'hidden', 1);
            
            // Create canvas element for plotting
            const plotHtml = `
                <div class="form-group">
                    <div class="clearfix">
                        <label class="control-label">Retina Location Plot</label>
                    </div>
                    <div class="control-input-wrapper">
                        <canvas id="plotCanvas" width="300" height="300" style="border: 1px solid #ddd; border-radius: 4px;"></canvas>
                        <div style="margin-top: 10px; display: flex; gap: 20px; font-size: 12px;">
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 50%; background-color: #27ae60;"></div>
                                <span>Screen Gaze</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 50%; background-color: #e74c3c;"></div>
                                <span>Away Gaze</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 50%; background-color: #f1c40f;"></div>
                                <span>Distracted Gaze</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Insert the canvas after the retina_location_log field
            $(frm.fields_dict.retina_location_log.wrapper).after(plotHtml);
            
            // Draw the plot
            setTimeout(() => {
                drawRetinaPlot(frm.doc.retina_location_log);
            }, 100);
        }
    },
});

function drawRetinaPlot(retinaData) {
    const canvas = document.getElementById('plotCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const plotWidth = canvas.width;
    const plotHeight = canvas.height;
    
    // Parse the JSON data
    let data = [];
    try {
        data = JSON.parse(retinaData) || [];
    } catch (e) {
        console.error('Error parsing retina location data:', e);
        return;
    }

    // Clear canvas with simple background
    ctx.fillStyle = '#f8f8f8';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid lines for reference (3x3 grid)
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    ctx.beginPath();
    
    // Vertical grid lines (thirds)
    for (let i = 1; i < 3; i++) {
        const x = (plotWidth / 3) * i;
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
    }
    
    // Horizontal grid lines (thirds)
    for (let i = 1; i < 3; i++) {
        const y = (plotHeight / 3) * i;
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
    }
    ctx.stroke();

    // Plot retina tracking points
    data.forEach((point, index) => {
        const canvasX = point.x * plotWidth;
        const canvasY = point.y * plotHeight;
        
        // Set color based on gaze direction - bright colors for visibility
        let color;
        switch(point.gazeDirection) {
            case 'screen':
                color = '#27ae60'; // Green for screen gaze
                break;
            case 'away':
                color = '#e74c3c'; // Red for away gaze
                break;
            case 'distracted':
                color = '#f1c40f'; // Yellow for distracted gaze
                break;
            default:
                color = '#95a5a6'; // Gray for unknown/undefined
        }
        ctx.fillStyle = color;
        
        // Draw bigger point for visibility
        ctx.beginPath();
        ctx.arc(canvasX, canvasY, 12, 0, 2 * Math.PI);
        ctx.fill();
        
        // Add point number with better contrast
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 14px Arial';
        ctx.textAlign = 'center';
        ctx.fillText((index + 1).toString(), canvasX, canvasY + 5);
    });
}
