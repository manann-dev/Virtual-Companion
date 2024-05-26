window.onload = function() {
    loadCategoryButtonEventListener();

    // Check if the user has already clicked "Yes"
    var userHasConfirmed = document.cookie.split(';').some((item) => item.trim().startsWith('over18='));

    // If the user has not clicked "Yes", show the modal and overlay
    if (!userHasConfirmed) {
        var modal = document.getElementById("myModal");
        var overlay = document.getElementById("overlay");

        document.getElementById('yesButton').addEventListener('click', function() {
            modal.style.display = "none";
            overlay.style.display = "none";
            // Set a cookie that expires in 30 days
            var date = new Date();
            date.setTime(date.getTime() + (30 * 24 * 60 * 60 * 1000));
            var expires = "; expires=" + date.toUTCString();
            document.cookie = "over18=yes" + expires + "; path=/";
        });

        document.getElementById('noButton').addEventListener('click', function() {
            window.location.href = 'https://www.google.com/';
        });

        modal.style.display = "block";
        overlay.style.display = "block";
    }

    fetch('/is_premium')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            if (data.is_premium) {
                isUserPremium = true;
            } else {
                document.querySelectorAll('.prem-box input').forEach(input => {
                    input.disabled = true;
                });
            }
        })
        .catch((error) => {
            console.error('Error checking premium status:', error);
        });

    document.querySelector('.menu-button').addEventListener('click', function() {
        const sidebar = document.querySelector('.sidebar');
        sidebar.classList.toggle('active');
    });

    // Setup the report modal
    document.getElementById('reportImage').addEventListener('click', function() {
        document.getElementById('reportModal').style.display = 'block';
    });

    // Setup the send report button
    document.getElementById('sendReportButton').addEventListener('click', function() {
        var reportReason = document.getElementById('reportReason').value;
        sendReport(reportReason);
    });

    let isUserPremium = false; // Initial value, assuming the user is not premium.
    let countdown = 79; // Start with a delay of 10 seconds
    let interval;
    let img = document.getElementById('generatedImgPath'); // Declare img variable at a higher scope

    function loadCategoryButtonEventListener() {
        const categories = document.querySelectorAll('.category-section-body');

        // Function to toggle active class
        const toggleActiveClass = (event) => {
            const children = event.currentTarget.children;
            for (let i = 0; i < children.length; i++) {
                const currentChild = children[i];
                if (currentChild.value == event.target.value) {
                    event.target.classList.add('active');
                } else {
                    currentChild.classList.remove('active');
                }
            }
        };

        // Add event listener to each category
        categories.forEach((category) => {
            category.addEventListener('click', toggleActiveClass);

            // Set the first button in each category as active by default
            if (category.children.length > 0) {
                category.children[0].classList.add('active');
            }
        });
    }

    let imagesToDisplay = null;
    let countdownFinished = false;
    let message = null;
    let currentUniqueId = null;

    function startQueueCountdown() {
        countdown = isUserPremium ? 25 : 79; // 30 seconds for premium users, 79 for others
        document.getElementById('queueSection').style.display = 'block';
        document.getElementById('skipLineOption').style.display = 'block';
        interval = setInterval(updateQueue, 1000);
    }

    function generateImage(textInput, negativePrompt, gender, ethnicity, hairColor, face, hairStyle, eyesColor,
        outfit, places, race, accessories, no_watermark, private_gallery, image_size, quality, img_grid, seed, currentUniqueId) {

        startQueueCountdown(); // Call the startQueueCountdown function

        const body = JSON.stringify({
            text_input: textInput,
            negative_prompt: negativePrompt,
            gender: gender,
            ethnicity: ethnicity,
            hairColor: hairColor,
            face: face,
            hairStyle: hairStyle,
            eyesColor: eyesColor,
            outfit: outfit,
            places: places,
            race: race,
            accessories: accessories,
            no_watermark: no_watermark,
            private_gallery: private_gallery,
            img_size: image_size,
            num_images: img_grid,
            quality: quality,
            seed: seed,
            uniqueId: currentUniqueId
        });
        console.log("=========  ", body);
        // Emit a socket event to send the data to the server
        socket.emit('generate_image', body);

        // Log the data being sent (optional, for debugging purposes)
        console.log("Data sent to the server: ", body);
    }

    function displayImages(images) {
        let imagesContainer = document.getElementById('imagesContainer');
        imagesContainer.innerHTML = ''; // Clear existing images

        images.forEach(image => {
            let img = document.createElement('img');
            img.src = image; // Assuming the image URL is in the 'url' field
            imagesContainer.appendChild(img);
        });
    }

    function updateQueue() {
        document.getElementById('generate_button').disabled = true;
        if (countdown > 0) {
            if (isUserPremium) {
                document.getElementById('queueStatus').textContent = `Your hentai is loading in... (${countdown}) seconds.`;
            } else {
                document.getElementById('queueStatus').textContent = `Your queue is up in (${countdown}) seconds.`;
            }
            countdown--;
        } else {
            countdownFinished = true;
            if (isUserPremium) {
                document.getElementById('queueStatus').textContent = 'Yay, your hentai loaded!';
            } else {
                document.getElementById('queueStatus').textContent = 'Your queue is now ready!';
            }

            clearInterval(interval);
            document.getElementById('skipLineOption').style.display = 'none'; // Hide the skip link when the queue is ready
            // console.log("images not null", countdownFinished, imagesToDisplay)
            if (countdownFinished && imagesToDisplay) {
                displayImages(imagesToDisplay); // Ensure you pass the appropriate arguments
                document.getElementById('queueStatus').textContent = message;
                document.getElementById('generate_button').disabled = false;
            } else {
                console.error('No images available to display.');
                document.getElementById('generate_button').disabled = false;
            }
        }
    }

    document.getElementById('open-info-popup').addEventListener('click', function() {
        document.getElementById('info-popup-container').style.display = 'block';
    });

    document.getElementById('close-info-popup').addEventListener('click', function() {
        document.getElementById('info-popup-container').style.display = 'none';
    });

    // Open the guide popup
    document.getElementById('open-guide-popup').addEventListener('click', function() {
        document.getElementById('guide-popup-container').style.display = 'block';
    });

    // Close the guide popup
    document.getElementById('close-guide-popup').addEventListener('click', function() {
        document.getElementById('guide-popup-container').style.display = 'none';
    });

    // Open the FAQ popup
    document.getElementById('open-faq-popup').addEventListener('click', function() {
        document.getElementById('faq-popup-container').style.display = 'block';
    });

    // Close the FAQ popup
    document.getElementById('close-faq-popup').addEventListener('click', function() {
        document.getElementById('faq-popup-container').style.display = 'none';
    });

    document.querySelectorAll('.feature-button').forEach(button => {
        button.addEventListener('click', function() {
            this.classList.toggle('active');
        });
    });

    const socket = io({autoConnect: false});

    socket.on('connect', function() {
        currentUniqueId = uuid.v4();
        console.log("Socket connected from frontend!! Track ID:", currentUniqueId);
        socket.emit('user_connected', { track_id: currentUniqueId });  // Changed event name here
    });

    socket.connect();

    socket.on("webhook", function(data) {
        console.log("++++webhook+++++", data);
        if (data.uniqueId === currentUniqueId) {
            if (data.status === 'success') {
                document.getElementById('queueStatus').textContent = 'Image successfully generated!';
                imagesToDisplay = data.images;
                message = 'Image generated.';
            } else if (data.status === 'rateLimitExceeded') {
                imagesToDisplay = ['https://aihentaigenerator.net/wp-content/uploads/2023/11/AIGDefaultimage1.png'];
                message = 'Image generation failed. Please try again.';
            } else if (data.status === 'error') {
                imagesToDisplay = ['https://aihentaigenerator.net/wp-content/uploads/2023/11/AIGDefaultimage1.png'];
                message = 'Image generation failed. Please try again.';
            }
            document.getElementById('generate_button').disabled = false;
            document.getElementById('skipLineOption').style.display = 'none';
        }
    });

    socket.on('receive_message', function(data) {
        console.log("Received data from server: ", data);
        var response = JSON.parse(data);
        var history = response.results[0].history.visible;

        // Display the conversation history
        var chatHistory = document.getElementById('chatHistory');
        chatHistory.innerHTML = '';
        history.forEach(function(message, index) {
            var messageElement = document.createElement('p');
            messageElement.textContent = message;
            chatHistory.appendChild(messageElement);
        });
    });

    socket.on('error', function(error) {
        console.error('Error received from server:', error);
    });

    // Setup the form submission
    var form = document.querySelector('form');
    form.addEventListener('submit', function(event) {
        event.preventDefault();

        // Get values from form
        var textInput = document.getElementById('text_input').value;
        var negativePrompt = document.getElementById('navigate_prompt_image').value;
        var gender = document.querySelector('.gender .active')?.value || '';
        var ethnicity = document.querySelector('.ethnicity .active')?.value || '';
        var hairColor = document.querySelector('.hairColor .active')?.value || '';
        var face = document.querySelector('.face .active')?.value || '';
        var hairStyle = document.querySelector('.hairStyle .active')?.value || '';
        var eyesColor = document.querySelector('.eyesColor .active')?.value || '';
        var outfit = document.querySelector('.outfit .active')?.value || '';
        var places = document.querySelector('.places .active')?.value || '';
        var race = document.querySelector('.race .active')?.value || '';
        var accessories = document.querySelector('.accessories .active')?.value || '';
        var no_watermark = document.querySelector('.no_watermark .active')?.value || '';
        var private_gallery = document.querySelector('.private_gallery .active')?.value || '';
        var image_size = document.querySelector('.image_size .active')?.value || '';
        var quality = document.querySelector('.quality .active')?.value || '';
        var img_grid = document.querySelector('.img_grid .active')?.value || '';
        var seed = document.getElementById('seed').value || null;

        // Generate Image
        generateImage(textInput, negativePrompt, gender, ethnicity, hairColor, face, hairStyle, eyesColor,
            outfit, places, race, accessories, no_watermark, private_gallery, image_size, quality, img_grid, seed, currentUniqueId);
    });

    // Example of a form submission handler for the `send_message` event
    var chatForm = document.querySelector('#chatForm');
    if (chatForm) {
        chatForm.addEventListener('submit', function(event) {
            event.preventDefault();

            // Get values from form
            var question = document.getElementById('question').value;
            var character = document.getElementById('character').value;
            var state = {
                ban_eos_token: false,
                custom_token_bans: false,
                auto_max_new_tokens: false
            };

            // Send the message via socket
            sendMessage(question, character, state);
        });
    }
}

function sendReport(reportReason) {
    var trackingId = document.getElementById('trackingIdContainer').getAttribute('data-tracking-id');
    fetch('/report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                reason: reportReason,
                tracking_id: trackingId
            }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                // Handle server-side error
                console.error('Server error:', data.error);
            } else {
                // Close the report modal
                document.getElementById('reportModal').style.display = 'none';
            }
        })
        .catch((error) => {
            console.error('Fetch error:', error);
        });
}

// Login form handling
if (document.getElementById('loginForm')) {
    document.getElementById('loginForm').addEventListener('submit', function(event) {
        var email = document.getElementById('loginEmail').value;
        var password = document.getElementById('loginPassword').value;
        var confirmTerms = document.getElementById('confirm-terms-login'); // Adjust the ID accordingly

        if (email === '' || password === '') {
            event.preventDefault();
            alert('Please fill in all fields!');
        } else if (!confirmTerms.checked) {
            event.preventDefault();
            alert('You must agree to the terms and conditions before logging in.');
        }
    });
}

// Create account form handling
if (document.getElementById('createAccountForm')) {
    document.getElementById('createAccountForm').addEventListener('submit', function(event) {
        var nickname = document.getElementById('nickname').value;
        var email = document.getElementById('signupEmail').value;
        var password = document.getElementById('signupPassword').value;
        var confirmPassword = document.getElementById('confirmPassword').value;
        var confirmTerms = document.getElementById('confirm-terms-create'); // Adjust the ID accordingly

        if (nickname === '' || email === '' || password === '' || confirmPassword === '') {
            event.preventDefault();
            alert('Please fill in all fields!');
        } else if (password !== confirmPassword) {
            event.preventDefault();
            alert('Passwords do not match!');
        } else if (!confirmTerms.checked) {
            event.preventDefault();
            alert('You must agree to the terms and conditions before creating an account.');
        }
    });
}

// Fetching more images function
function fetchMoreImages(page) {
    // Use your API endpoint
    fetch('/api/gallery?page=' + page)
        .then(response => response.json())
        .then(data => {
            // Append new images to the gallery
            data.forEach(image => {
                const galleryItem = document.createElement('div');
                galleryItem.className = 'gallery-item';
                // Construct gallery item innerHTML similar to the template in HTML
                // ...
                galleryElement.appendChild(galleryItem);
            });
        });
}

let currentPage = 1;
let currentFilter = 'all'; // default filter
const galleryContainerElement = document.querySelector('.gallery.container-fluid');

function fetchPublicGallery() {
    fetchImages(false);
}

function fetchPrivateGallery() {
    fetchImages(true);
}

function fetchImages(private = false) {
    let endpoint;
    if (private) {
        endpoint = `/api/gallery?page=${currentPage}&filter_type=${currentFilter}&gallery_type=private`;
    } else {
        endpoint = `/api/gallery?page=${currentPage}&filter_type=${currentFilter}`;
    }

    fetch(endpoint)
        .then(response => response.json())
        .then(data => {
            // Clear the gallery if we're on the first page (e.g., when a new filter is applied)
            if (currentPage === 1) {
                galleryContainerElement.innerHTML = ''; // clear the gallery
            }

            data.forEach(image => {
                const galleryItem = document.createElement('div');
                galleryItem.className = 'gallery-item col-12 col-md-6 col-lg-4 col-xl-3';
                galleryItem.setAttribute('data-image-id', image.id);
                galleryItem.innerHTML = `
                   <a href="https://www.aihentaigenerator.net/?image_id=${image.id}" class="gallery-link">
                        <div class="image-wrapper">
                            <img src="${image.url}" class="gallery-images" alt="Generated Image">
                        </div>
                        <div class="gallery-overlay">
                            <span class="gallery-text">${image.text_input || "No description"}</span>
                        </div>
                    </a>
                    <div class="gallery-stats">
                        <span class="gallery-likes">
                            <i class="fas fa-heart"></i>
                            ${image.likes}
                        </span>
                        <span class="gallery-views">
                            <i class="fas fa-eye"></i>
                            ${image.views}
                        </span>
                    </div>`;
                galleryContainerElement.appendChild(galleryItem);
            });
        });
}

// Handle infinite scroll
window.addEventListener('scroll', function() {
    if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight) {
        currentPage++;
        fetchImages();
    }
});

// Handle filter buttons
document.querySelectorAll('.filter-button').forEach(button => {
    button.addEventListener('click', function() {
        currentFilter = button.getAttribute('data-filter');
        currentPage = 1;
        fetchImages();
    });
});

document.querySelector('.gallery').addEventListener('click', function(event) {
    // Check if a gallery item (image) was clicked to update views
    if (event.target.closest('.gallery-item')) {
        const item = event.target.closest('.gallery-item');
        const imageId = item.getAttribute('data-image-id');

        if (imageId) {
            fetch('/api/update-views', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        image_id: imageId
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const viewsSpan = item.querySelector('.gallery-views');
                        viewsSpan.textContent = `${data.views} Views`;
                    }
                });
        }
    }

    // Check if a like icon was clicked to update likes
    if (event.target.matches('.gallery-likes i')) {
        const icon = event.target;
        const imageId = icon.closest('.gallery-item').getAttribute('data-image-id');

        fetch('/api/update-likes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    image_id: imageId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const likesSpan = icon.parentElement;
                    likesSpan.textContent = `${data.likes} Likes`;
                }
            });
    }
});

document.addEventListener("DOMContentLoaded", function() {
    document.getElementById("checkout-button").addEventListener("click", function() {
        var stripe_public_key = 'pk_live_51OE5GSJInIllC3Fua25gYYTtNpYvGQOo8VhNBCDDoNjwYdwuAJQr7ebxgkOKwzG3kZw88jLVmtVrIbxr3SNVlihy00RDGOJUTx';
        // Make a POST request to your server to get the session ID
        fetch('/create-checkout-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                // Add any necessary data in the request body
                body: JSON.stringify({
                    // Include user information or other details here if needed
                }),
            })
            .then(response => {
                if (!response.ok && response.status === 401) {
                    return response.json(); // If not authorized, expect a JSON response with redirect info
                }
                return response.json(); // Continue with the original processing
            })
            .then(function(data) {
                if (data.redirect) {
                    // If the JSON indicates a redirect, perform the redirect in the browser
                    window.location.href = data.redirect_url;
                    return;
                }

                // Use the session ID obtained from the server
                var sessionId = data.sessionId;

                // Redirect to the Checkout page
                var stripe = Stripe(stripe_public_key);
                stripe.redirectToCheckout({
                    sessionId: sessionId, // Use the obtained session ID

                }).then(function(result) {
                    if (result.error) {
                        var displayError = document.getElementById('error-message');
                        displayError.textContent = result.error.message;
                    }
                });
            })
            .catch(function(error) {
                console.error('Error:', error);
            });
    });
});

function sendMessage(question, character, state) {
    const data = {
        question: question,
        character: character,
        state: state
    };
    socket.emit('send_message', data);
    console.log("Data sent to the server: ", data);
}
