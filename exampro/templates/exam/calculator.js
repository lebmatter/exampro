frappe.ready(() => {
    updateResult(0);
    document.addEventListener('keydown', handleKeyboardInput);

    $card = $('#calcCard');
    $card.on('focusin', function() {
        $(this).addClass('focus-ring');
    });

    $card.on('focusout', function() {
        $(this).removeClass('focus-ring');
    });

    $('.calcBtn').on('mousedown', function(e) {
        const key = $(this).data('key');
        dispatchKeyEvent(key);
        e.preventDefault(); // Prevent default mousedown behavior after handling the event
    });
});

function handleKeyboardInput(event) {
    $card = $('#calcCard');
    if ($card.is(':focus') || $card.find(':focus').length > 0) {
        const key = event.key;
        if (/[0-9.]/.test(key)) {
            appendNumber(key);
        } else if (['+', '-', '*', '/', '%'].includes(key)) {
            appendSymbol(key);
        } else if (key === 'Enter' || key === '=') {
            calculateResult();
        } else if (key === 'Backspace') {
            let currentResult = getCurrentResult();
            updateResult(currentResult.slice(0, -1) || '0');
        } else if (key === 'Escape' || key === 'c') {
            clearResult();
        }
}}

const getCurrentResult = () => {
    const resultElement = document.getElementById('calcResult');
    return resultElement.value;
};
const updateResult = (newResult) => {
    $("#calcResult").val(newResult);
};

const showResult = (newResult) => {
    // Remove trailing symbols                                                                                                                                                                                                                                                                               
    newResult = newResult.toString().replace(/[+\-*/%.]$/, ''); 
    $("#calcResult").val(newResult);
};

const calculateResult = () => {
    let currentResult = getCurrentResult();
    // sanitize current result with regex
    var pattern = /^[-+*/%0-9.]*$/;
    if (!pattern.test(currentResult)) {
        updateResult("Error: Invalid characters");
        return;
    }
    
    try {
        currentResult = currentResult.replace(/%/g, '/100');
        let evaluatedResult = eval(currentResult);
        if (!isFinite(evaluatedResult)) {
            updateResult("Error");
        } else {
            showResult(evaluatedResult);
        }
    } catch (error) {
        updateResult('Error');
    }
};

const appendSymbol = symbol => {
    let currentResult = getCurrentResult();
    // sanitize current result with regex
    var pattern = /^[-+*/%0-9.]*$/;
    if (!pattern.test(currentResult)) {
        updateResult("Error: Invalid characters");
        return;
    }
    
    // Check if the current result ends with a non-numeric symbol
    if (/[-+*/%]$/.test(currentResult)) {
        // If it does, replace the last symbol with the new one
        updateResult(currentResult.slice(0, -1) + symbol);
    } else {
        // If it doesn't, append the new symbol
        updateResult(currentResult + symbol);
    }
};

const appendNumber = number => {
    let currentResult = getCurrentResult();
    if (currentResult === "0") {
        newResult = number;
    } else {
        newResult = currentResult + number;
    }
    updateResult(newResult);
};

const clearResult = () => {
    updateResult(0);
};

const dispatchKeyEvent = (key) => {
    // Only dispatch events for valid calculator inputs
    $card = $('#calcCard');
    if (!$card.is(':focus') && $card.find(':focus').length === 0) {
        $card.focus();
    }
    if (/^[0-9+\-*/%=.]$/.test(key) || key === 'Escape') {
        const event = new KeyboardEvent('keydown', {
            key: key,
            bubbles: true,
            cancelable: true,
        });
        document.dispatchEvent(event);
    }
};
