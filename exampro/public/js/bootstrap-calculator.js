/**
 * Bootstrap Calculator - Standalone Calculator Library
 * Renders a functional calculator UI with Bootstrap 5 classes
 * 
 * GitHub Repository: https://github.com/lebmatter/bootstrap-calculator
 * 
 * Usage:
 * const calculator = new BootstrapCalculator('.calculator-container');
 * calculator.init();
 */

class BootstrapCalculator {
    constructor(containerSelector) {
        this.containerSelector = containerSelector;
        this.container = null;
        this.resultInput = null;
        this.isInitialized = false;
    }

    init() {
        this.container = document.querySelector(this.containerSelector);
        if (!this.container) {
            console.error(`Calculator container not found: ${this.containerSelector}`);
            return;
        }

        this.render();
        this.attachEventListeners();
        this.updateResult('0');
        this.isInitialized = true;
    }

    render() {
        const calculatorHTML = `
            <div class="calculator-wrapper">
                <div class="card border-0 shadow-sm">
                    <div class="card-body p-3">
                        <div class="calculator">
                            <!-- Display -->
                            <div class="row mb-3">
                                <div class="col-12">
                                    <input type="text" class="form-control form-control-lg text-end calc-display" readonly>
                                </div>
                            </div>
                            
                            <!-- Clear, Percent, Divide -->
                            <div class="row mb-2">
                                <div class="col-12">
                                    <div class="btn-group d-flex" role="group">
                                        <button class="btn btn-outline-secondary flex-fill calc-btn" data-key="Escape">C</button>
                                        <button class="btn btn-outline-secondary flex-fill calc-btn" data-key="%">%</button>
                                        <button class="btn btn-outline-primary flex-fill calc-btn" data-key="/">÷</button>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Multiply, Minus, Plus -->
                            <div class="row mb-2">
                                <div class="col-12">
                                    <div class="btn-group d-flex" role="group">
                                        <button class="btn btn-outline-primary flex-fill calc-btn" data-key="*">×</button>
                                        <button class="btn btn-outline-primary flex-fill calc-btn" data-key="-">−</button>
                                        <button class="btn btn-outline-primary flex-fill calc-btn" data-key="+">+</button>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Numbers 7, 8, 9 -->
                            <div class="row mb-2">
                                <div class="col-12">
                                    <div class="btn-group d-flex" role="group">
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="7">7</button>
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="8">8</button>
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="9">9</button>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Numbers 4, 5, 6 -->
                            <div class="row mb-2">
                                <div class="col-12">
                                    <div class="btn-group d-flex" role="group">
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="4">4</button>
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="5">5</button>
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="6">6</button>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Numbers 1, 2, 3 -->
                            <div class="row mb-2">
                                <div class="col-12">
                                    <div class="btn-group d-flex" role="group">
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="1">1</button>
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="2">2</button>
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="3">3</button>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Decimal, 0, Equals -->
                            <div class="row">
                                <div class="col-12">
                                    <div class="btn-group d-flex" role="group">
                                        <button class="btn btn-light flex-fill calc-btn" data-key=".">.</button>
                                        <button class="btn btn-light flex-fill calc-btn number-btn" data-key="0">0</button>
                                        <button class="btn btn-primary flex-fill calc-btn" data-key="=">=</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.container.innerHTML = calculatorHTML;
        this.resultInput = this.container.querySelector('.calc-display');
    }

    attachEventListeners() {
        // Button click events
        const buttons = this.container.querySelectorAll('.calc-btn');
        buttons.forEach(button => {
            button.addEventListener('click', (e) => {
                const key = e.target.getAttribute('data-key');
                this.handleInput(key);
                e.preventDefault();
            });
        });

        // Keyboard events
        document.addEventListener('keydown', (event) => {
            if (this.container.contains(document.activeElement) || 
                this.container === document.activeElement) {
                this.handleKeyboardInput(event);
            }
        });

        // Focus events for keyboard support
        this.container.addEventListener('click', () => {
            this.container.focus();
        });

        // Make container focusable
        this.container.setAttribute('tabindex', '0');
        this.container.style.outline = 'none';
    }

    handleKeyboardInput(event) {
        const key = event.key;
        
        if (/[0-9.]/.test(key)) {
            this.handleInput(key);
            event.preventDefault();
        } else if (['+', '-', '*', '/', '%'].includes(key)) {
            this.handleInput(key);
            event.preventDefault();
        } else if (key === 'Enter' || key === '=') {
            this.handleInput('=');
            event.preventDefault();
        } else if (key === 'Backspace') {
            this.handleBackspace();
            event.preventDefault();
        } else if (key === 'Escape' || key.toLowerCase() === 'c') {
            this.handleInput('Escape');
            event.preventDefault();
        }
    }

    handleInput(key) {
        if (!this.isInitialized) return;

        if (/[0-9.]/.test(key)) {
            this.appendNumber(key);
        } else if (['+', '-', '*', '/', '%'].includes(key)) {
            this.appendSymbol(key);
        } else if (key === '=' || key === 'Enter') {
            this.calculateResult();
        } else if (key === 'Escape') {
            this.clearResult();
        }
    }

    getCurrentResult() {
        return this.resultInput.value;
    }

    updateResult(newResult) {
        this.resultInput.value = newResult;
    }

    showResult(newResult) {
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
        this.updateResult(newResult);
    }

    calculateResult() {
        let currentResult = this.getCurrentResult();
        
        // Skip if already showing an error
        if (currentResult.includes('Error')) {
            return;
        }
        
        // Sanitize input - only allow valid calculator characters
        const pattern = /^[-+*/%0-9.]*$/;
        if (!pattern.test(currentResult)) {
            this.updateResult("Error: Invalid characters");
            return;
        }
        
        try {
            // Handle percentage calculations properly
            currentResult = this.handlePercentageCalculation(currentResult);
            
            // Use safe evaluation instead of eval
            let evaluatedResult = this.safeEvaluate(currentResult);
            
            if (!isFinite(evaluatedResult)) {
                this.updateResult("Error: Invalid result");
            } else {
                this.showResult(evaluatedResult);
            }
        } catch (error) {
            this.updateResult('Error: Invalid expression');
        }
    }

    // Safe mathematical expression evaluator (replaces eval)
    safeEvaluate(expression) {
        // Remove any whitespace
        expression = expression.replace(/\s/g, '');
        
        // Check for division by zero
        if (/\/0(?!\d)/.test(expression)) {
            throw new Error('Division by zero');
        }
        
        // Parse and evaluate with proper operator precedence
        return this.evaluateExpression(expression);
    }

    // Simple expression parser with operator precedence
    evaluateExpression(expr) {
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
    }

    handlePercentageCalculation(expression) {
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
    }

    appendSymbol(symbol) {
        let currentResult = this.getCurrentResult();
        
        // Clear error state when starting new calculation
        if (currentResult.includes('Error')) {
            currentResult = '0';
        }
        
        // Sanitize input
        if (!/^[-+*/%0-9.]*$/.test(currentResult)) {
            this.updateResult("0");
            return;
        }
        
        // Don't allow operators at the start (except minus for negative numbers)
        if (currentResult === '0' && symbol !== '-') {
            return;
        }
        
        // Handle consecutive operators
        if (/[-+*/%]$/.test(currentResult)) {
            this.updateResult(currentResult.slice(0, -1) + symbol);
        } else {
            this.updateResult(currentResult + symbol);
        }
    }

    appendNumber(number) {
        let currentResult = this.getCurrentResult();
        
        // Clear error state when starting new calculation
        if (currentResult.includes('Error')) {
            this.updateResult(number);
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
            if (currentNumber === '' || /[+\-*/%]$/.test(currentResult)) {
                this.updateResult(currentResult + '0.');
                return;
            }
        }
        
        // Replace initial zero with the new number (unless it's a decimal)
        if (currentResult === '0' && number !== '.') {
            this.updateResult(number);
        } else {
            this.updateResult(currentResult + number);
        }
    }

    handleBackspace() {
        let currentResult = this.getCurrentResult();
        
        // Clear error state
        if (currentResult.includes('Error')) {
            this.updateResult('0');
            return;
        }
        
        // Remove last character or reset to 0
        const newResult = currentResult.slice(0, -1);
        this.updateResult(newResult || '0');
    }

    clearResult() {
        this.updateResult('0');
    }

    // Public methods for external control
    clear() {
        this.clearResult();
    }

    getValue() {
        return this.getCurrentResult();
    }

    setValue(value) {
        this.updateResult(value.toString());
    }

    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.isInitialized = false;
    }
}

// Export for both CommonJS and ES6 modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BootstrapCalculator;
}

// Also make available globally
if (typeof window !== 'undefined') {
    window.BootstrapCalculator = BootstrapCalculator;
}