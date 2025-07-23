frappe.ready(() => {
    updateResult('0');
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
        e.preventDefault();
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
            handleBackspace();
        } else if (key === 'Escape' || key === 'c') {
            clearResult();
        }
    }
}

const getCurrentResult = () => {
    const resultElement = document.getElementById('calcResult');
    return resultElement.value;
};

const updateResult = (newResult) => {
    $("#calcResult").val(newResult);
};

const showResult = (newResult) => {
    // Format large numbers and remove trailing symbols
    if (typeof newResult === 'number') {
        if (Math.abs(newResult) >= 1e15) {
            newResult = newResult.toExponential(6);
        } else {
            // Remove unnecessary decimal places
            newResult = parseFloat(newResult.toFixed(10));
        }
    }
    newResult = newResult.toString().replace(/[+\-*/%.]$/, '');
    $("#calcResult").val(newResult);
};

const calculateResult = () => {
    let currentResult = getCurrentResult();
    
    // Skip if already showing an error
    if (currentResult.includes('Error')) {
        return;
    }
    
    // Sanitize input - only allow valid calculator characters
    const pattern = /^[-+*/%0-9.]*$/;
    if (!pattern.test(currentResult)) {
        updateResult("Error: Invalid characters");
        return;
    }
    
    try {
        // Handle percentage calculations properly
        currentResult = handlePercentageCalculation(currentResult);
        
        // Use safe evaluation instead of eval
        let evaluatedResult = safeEvaluate(currentResult);
        
        if (!isFinite(evaluatedResult)) {
            updateResult("Error: Invalid result");
        } else {
            showResult(evaluatedResult);
        }
    } catch (error) {
        updateResult('Error: Invalid expression');
    }
};

// Safe mathematical expression evaluator (replaces eval)
const safeEvaluate = (expression) => {
    // Remove any whitespace
    expression = expression.replace(/\s/g, '');
    
    // Check for division by zero
    if (/\/0(?!\d)/.test(expression)) {
        throw new Error('Division by zero');
    }
    
    // Parse and evaluate with proper operator precedence
    return evaluateExpression(expression);
};

// Simple expression parser with operator precedence
const evaluateExpression = (expr) => {
    // Split into tokens
    const tokens = expr.match(/(\d*\.?\d+|[+\-*/])/g);
    if (!tokens) return 0;
    
    // Handle multiplication and division first
    for (let i = 1; i < tokens.length; i += 2) {
        if (tokens[i] === '*' || tokens[i] === '/') {
            const left = parseFloat(tokens[i - 1]);
            const right = parseFloat(tokens[i + 1]);
            const result = tokens[i] === '*' ? left * right : left / right;
            
            tokens.splice(i - 1, 3, result.toString());
            i -= 2; // Adjust index after splice
        }
    }
    
    // Handle addition and subtraction
    let result = parseFloat(tokens[0]);
    for (let i = 1; i < tokens.length; i += 2) {
        const operator = tokens[i];
        const operand = parseFloat(tokens[i + 1]);
        
        if (operator === '+') result += operand;
        else if (operator === '-') result -= operand;
    }
    
    return result;
};

const handlePercentageCalculation = (expression) => {
    // Handle cases like "1200+18%" or "1200-18%"
    const percentPattern = /(\d+(?:\.\d+)?)\s*([+\-])\s*(\d+(?:\.\d+)?)%/g;
    
    return expression.replace(percentPattern, (match, baseNumber, operator, percentValue) => {
        const base = parseFloat(baseNumber);
        const percent = parseFloat(percentValue);
        const percentageAmount = (base * percent) / 100;
        
        if (operator === '+') {
            return (base + percentageAmount).toString();
        } else if (operator === '-') {
            return (base - percentageAmount).toString();
        }
        return match;
    }).replace(/%/g, '/100'); // Handle remaining % as division by 100
};

const appendSymbol = symbol => {
    let currentResult = getCurrentResult();
    
    // Clear error state when starting new calculation
    if (currentResult.includes('Error')) {
        currentResult = '0';
    }
    
    // Sanitize input
    if (!/^[-+*/%0-9.]*$/.test(currentResult)) {
        updateResult("0");
        return;
    }
    
    // Don't allow operators at the start (except minus for negative numbers)
    if (currentResult === '0' && symbol !== '-') {
        return;
    }
    
    // Handle consecutive operators
    if (/[-+*/%]$/.test(currentResult)) {
        updateResult(currentResult.slice(0, -1) + symbol);
    } else {
        updateResult(currentResult + symbol);
    }
};

const appendNumber = number => {
    let currentResult = getCurrentResult();
    
    // Clear error state when starting new calculation
    if (currentResult.includes('Error')) {
        updateResult(number);
        return;
    }
    
    // Handle decimal point validation
    if (number === '.') {
        // Find the current number being entered
        const parts = currentResult.split(/[+\-*/%]/);
        const currentNumber = parts[parts.length - 1];
        
        // Don't allow multiple decimal points in the same number
        if (currentNumber.includes('.')) {
            return;
        }
        
        // Add leading zero if decimal point is first
        if (currentNumber === '' || currentResult.endsWith(/[+\-*/%]/)) {
            updateResult(currentResult + '0.');
            return;
        }
    }
    
    // Replace initial zero with the new number (unless it's a decimal)
    if (currentResult === '0' && number !== '.') {
        updateResult(number);
    } else {
        updateResult(currentResult + number);
    }
};

const handleBackspace = () => {
    let currentResult = getCurrentResult();
    
    // Clear error state
    if (currentResult.includes('Error')) {
        updateResult('0');
        return;
    }
    
    // Remove last character or reset to 0
    const newResult = currentResult.slice(0, -1);
    updateResult(newResult || '0');
};

const clearResult = () => {
    updateResult('0');
};

const dispatchKeyEvent = (key) => {
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