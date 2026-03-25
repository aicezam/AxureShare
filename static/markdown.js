/**
 * Axure 自动 Markdown 渲染插件
 */

(function() {
    'use strict';

    var debugMode = true;

    function log(msg) {
        if (debugMode && console && console.log) {
            console.log('[AxureMarkdown] ' + msg);
        }
    }

    function error(msg) {
        if (console && console.error) {
            console.error('[AxureMarkdown] ' + msg);
        }
    }

    function loadScript(src, onSuccess, onError) {
        if (typeof $axure !== 'undefined' && $axure.utils && $axure.utils.loadJS) {
            log('Using $axure.utils.loadJS: ' + src);
            var success = $axure.utils.loadJS(src);
            if (success && onSuccess) {
                setTimeout(onSuccess, 0);
            } else if (!success && onError) {
                setTimeout(onError, 0);
            }
            return;
        }

        var script = document.createElement('script');
        script.type = 'text/javascript';
        script.src = src;
        script.onload = function() {
            log('Loaded: ' + src);
            if (onSuccess) onSuccess();
        };
        script.onerror = function() {
            error('Failed to load: ' + src);
            if (onError) onError();
        };
        document.head.appendChild(script);
        log('Injecting script (fallback): ' + src);
    }

    function injectStyles() {
        var css =[
            '.axure-markdown-container { text-align: left; padding: 10px; overflow: auto; height: 100%; box-sizing: border-box; font-family: -apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,\'Helvetica Neue\',Arial,\'Noto Sans\',\'Liberation Sans\',sans-serif; }',
            '.axure-markdown-container h1, .axure-markdown-container h2, .axure-markdown-container h3, .axure-markdown-container h4, .axure-markdown-container h5, .axure-markdown-container h6 { font-weight: 600; margin-top: 1em; margin-bottom: 0.5em; line-height: 1.2; color: #111827; }',
            '.axure-markdown-container h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }',
            '.axure-markdown-container h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }',
            '.axure-markdown-container h3 { font-size: 1.25em; }',
            '.axure-markdown-container p { margin-top: 0; margin-bottom: 1em; line-height: 1.6; color: #374151; }',
            '.axure-markdown-container a { color: #2563eb; text-decoration: none; }',
            '.axure-markdown-container a:hover { text-decoration: underline; }',
            '.axure-markdown-container ul, .axure-markdown-container ol { margin-top: 0; margin-bottom: 1em; padding-left: 2em; }',
            '.axure-markdown-container ul { list-style-type: disc; }',
            '.axure-markdown-container ol { list-style-type: decimal; }',
            '.axure-markdown-container li { margin-top: 0.25em; line-height: 1.6; display: list-item; }',
            '.axure-markdown-container blockquote { margin: 0 0 1em 0; padding: 0 1em; color: #6a737d; border-left: 0.25em solid #dfe2e5; }',
            '.axure-markdown-container code { padding: 0.2em 0.4em; margin: 0; font-size: 85%; background-color: rgba(27,31,35,0.05); border-radius: 3px; font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace; }',
            '.axure-markdown-container pre { padding: 16px; overflow: auto; font-size: 85%; line-height: 1.45; background-color: #f6f8fa; border-radius: 6px; }',
            '.axure-markdown-container pre code { padding: 0; margin: 0; font-size: 100%; background-color: transparent; border: 0; }',
            '.axure-markdown-container table { border-spacing: 0; border-collapse: collapse; margin-top: 0; margin-bottom: 1em; width: 100%; overflow: auto; }',
            '.axure-markdown-container table th, .axure-markdown-container table td { padding: 6px 13px; border: 1px solid #dfe2e5; }',
            '.axure-markdown-container table tr:nth-child(2n) { background-color: #f6f8fa; }'
        ].join('');

        var style = document.createElement('style');
        style.type = 'text/css';
        if (style.styleSheet) {
            style.styleSheet.cssText = css;
        } else {
            style.appendChild(document.createTextNode(css));
        }
        document.head.appendChild(style);
        log('Styles injected');
    }

    function getTextContent(el) {
        if (!el) return '';
        
        var clone = el.cloneNode(true);
        var brs = clone.querySelectorAll('br');
        brs.forEach(function(br) {
            br.parentNode.replaceChild(document.createTextNode('\n'), br);
        });
        var blocks = clone.querySelectorAll('p, div, li, h1, h2, h3, h4, h5, h6');
        blocks.forEach(function(block) {
            block.appendChild(document.createTextNode('\n\n'));
        });
        var text = clone.textContent || '';
        text = text.replace(/\u00A0/g, ' '); 
        text = text.replace(/\u200B/g, '');  
        text = text.replace(/\n{3,}/g, '\n\n');
        text = text.replace(/(\|\s*)\n{2,}(?=\s*\|)/g, '$1\n');

        return text.trim();
    }

    function renderMermaid(blocks) {
        blocks.forEach(function(block) {
            var pre = block.parentElement;
            var mermaidDiv = document.createElement('div');
            mermaidDiv.className = 'mermaid';

            var codeText = block.innerHTML
                .replace(/&nbsp;/g, ' ')
                .replace(/<br\s*[\/]?>/gi, '\n')
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&amp;/g, '&');

            if (codeText.indexOf('\n') === -1) {
                codeText = codeText.replace(/\s+(graph|pie|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|info|flowchart)\s+/g, '\n$1 ');
                codeText = codeText.replace(/\s+(-->|---|-.->|==>)\s+/g, ' $1 ');
            }

            var fallbackText = (block.innerText || block.textContent || '').replace(/\u00A0/g, ' ');
            mermaidDiv.textContent = fallbackText.indexOf('\n') !== -1 ? fallbackText : codeText;

            if (pre && pre.parentElement) {
                pre.parentElement.replaceChild(mermaidDiv, pre);
            }
        });

        if (typeof mermaid !== 'undefined' && mermaid.run) {
            mermaid.run({ querySelector: '.mermaid' });
            log('Mermaid rendered');
        }
    }

    function renderAxureMarkdown() {
        if (typeof marked === 'undefined') {
            log('marked not loaded yet, waiting...');
            return false;
        }

        var selectors = [
            '[data-label="markdown.axure.share"]',
            '[data-label="Markdown.axure.share"]',
            '[data-label="MDAS"]',
            '[data-label="mdAS"]'
        ];

        var mdElements = document.querySelectorAll(selectors.join(','));
        log('Found ' + mdElements.length + ' markdown elements');

        if (mdElements.length === 0) {
            return false;
        }

        mdElements.forEach(function(el) {
            if (el.dataset.mdRendered) return;

            var textContainer = el.querySelector('.text');
            if (!textContainer) {
                log('No .text container found in element');
                return;
            }

            var rawText = getTextContent(textContainer);
            if (!rawText) return;

            // 渲染 HTML
            var html = marked.parse(rawText);
            textContainer.innerHTML = '<div class="axure-markdown-container">' + html + '</div>';
            el.dataset.mdRendered = 'true';
            
            var links = textContainer.querySelectorAll('a');
            links.forEach(function(link) {
                // 如果需要确保只有 http(s) 链接打开新窗口，可以加个判断： if (link.href.startsWith('http')) 
                link.setAttribute('target', '_blank');
                link.setAttribute('rel', 'noopener noreferrer');
            });
            
            log('Rendered markdown for element');

            var mermaidBlocks = textContainer.querySelectorAll('code.language-mermaid');
            if (mermaidBlocks.length > 0) {
                log('Found ' + mermaidBlocks.length + ' mermaid blocks');
                renderMermaid(Array.from(mermaidBlocks));
            }
        });

        return true;
    }

    function init() {
        log('Initializing...');

        if (typeof mermaid !== 'undefined' && mermaid.initialize) {
            mermaid.initialize({ startOnLoad: false, theme: 'default' });
        }

        injectStyles();

        var retryCount = 0;
        var maxRetries = 100;
        var retryInterval = 100;

        function tryRender() {
            if (renderAxureMarkdown()) {
                log('Initial render complete');
                return;
            }

            retryCount++;
            if (retryCount < maxRetries) {
                setTimeout(tryRender, retryInterval);
            } else {
                error('Max retries reached, marked may not be loaded properly');
            }
        }

        tryRender();

        if (window.MutationObserver) {
            var observer = new MutationObserver(function(mutations) {
                var shouldRender = false;
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        shouldRender = true;
                    }
                });
                if (shouldRender) {
                    retryCount = 0;
                    tryRender();
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
            log('MutationObserver attached');
        }
    }

    function start() {
        log('Starting AxureMarkdown plugin...');
        log('Current URL: ' + window.location.href);
        log('Protocol: ' + window.location.protocol);

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    }

    start();
})();