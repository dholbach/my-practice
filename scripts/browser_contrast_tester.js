/**
 * Dark Theme Contrast Tester
 * Füge diesen Code in die Browser Developer Console ein, um Kontrastprobleme zu identifizieren.
 *
 * Usage:
 * 1. Öffne die Seite im Browser
 * 2. Öffne Developer Console (F12)
 * 3. Füge diesen Code ein und drücke Enter
 * 4. Rote Umrandungen zeigen problematische Elemente
 */

(function() {
    console.log('🔍 Dark Theme Contrast Checker');

    // 1. Dark Mode aktivieren
    const htmlEl = document.documentElement;
    const currentTheme = htmlEl.getAttribute('data-theme');

    if (currentTheme !== 'dark') {
        console.log('📱 Switching to dark theme...');
        htmlEl.setAttribute('data-theme', 'dark');
    } else {
        console.log('✓ Already in dark theme');
    }

    // 2. Privacy Mode aktivieren (optional - auskommentieren wenn nicht benötigt)
    // document.body.classList.add('privacy-mode');

    // 3. Kontrast-Verhältnis berechnen
    function getRelativeLuminance(rgb) {
        const [r, g, b] = rgb.match(/\d+/g).map(Number);
        const [rs, gs, bs] = [r, g, b].map(val => {
            const v = val / 255;
            return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
    }

    function getContrastRatio(color1, color2) {
        const l1 = getRelativeLuminance(color1);
        const l2 = getRelativeLuminance(color2);
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        return (lighter + 0.05) / (darker + 0.05);
    }

    // 4. Alle sichtbaren Text-Elemente prüfen
    const problems = [];
    const allElements = document.querySelectorAll('*');

    allElements.forEach(el => {
        // Nur Elemente mit sichtbarem Text
        const hasText = el.childNodes.length > 0 &&
                       Array.from(el.childNodes).some(node =>
                           node.nodeType === Node.TEXT_NODE &&
                           node.textContent.trim().length > 0
                       );

        if (!hasText) return;

        // Style auslesen
        const style = getComputedStyle(el);
        const isVisible = style.display !== 'none' &&
                         style.visibility !== 'hidden' &&
                         style.opacity !== '0';

        if (!isVisible) return;

        // Farben prüfen
        const color = style.color;
        const bgColor = style.backgroundColor;

        // Background vom Parent holen wenn transparent
        let actualBg = bgColor;
        if (bgColor === 'rgba(0, 0, 0, 0)' || bgColor === 'transparent') {
            let parent = el.parentElement;
            while (parent && (actualBg === 'rgba(0, 0, 0, 0)' || actualBg === 'transparent')) {
                actualBg = getComputedStyle(parent).backgroundColor;
                parent = parent.parentElement;
            }
        }

        // Kontrast berechnen
        if (actualBg && actualBg !== 'rgba(0, 0, 0, 0)' && actualBg !== 'transparent') {
            try {
                const contrast = getContrastRatio(color, actualBg);

                // WCAG AA: Normal text needs 4.5:1, large text 3:1
                const fontSize = parseFloat(style.fontSize);
                const minContrast = fontSize >= 18 || (fontSize >= 14 && style.fontWeight >= 700) ? 3 : 4.5;

                if (contrast < minContrast) {
                    const problem = {
                        element: el,
                        className: el.className,
                        id: el.id,
                        text: el.textContent.substring(0, 50),
                        color: color,
                        bgColor: actualBg,
                        contrast: contrast.toFixed(2),
                        required: minContrast
                    };

                    problems.push(problem);

                    // Visuell markieren
                    el.style.outline = '3px solid red';
                    el.style.outlineOffset = '2px';
                }
            } catch (e) {
                // Ignoriere Fehler bei Farbberechnung
            }
        }
    });

    // 5. Ergebnisse ausgeben
    console.log(`\n📊 Gefunden: ${problems.length} Kontrastprobleme\n`);

    if (problems.length > 0) {
        console.table(problems.map(p => ({
            'Element': `${p.element.tagName}.${p.className}`,
            'ID': p.id || '-',
            'Text': p.text,
            'Kontrast': p.contrast,
            'Erforderlich': p.required,
            'Status': parseFloat(p.contrast) < p.required ? '❌ Fail' : '✓ Pass'
        })));

        console.log('\n💡 Tipp: Problematische Elemente sind rot umrandet');
        console.log('🔄 Um Markierungen zu entfernen: location.reload()');
    } else {
        console.log('✅ Keine Kontrastprobleme gefunden!');
    }

    // 6. Zusammenfassung nach Klassen
    const byClass = {};
    problems.forEach(p => {
        const className = p.className || 'no-class';
        byClass[className] = (byClass[className] || 0) + 1;
    });

    if (Object.keys(byClass).length > 0) {
        console.log('\n📋 Probleme nach CSS-Klasse:');
        Object.entries(byClass)
            .sort((a, b) => b[1] - a[1])
            .forEach(([cls, count]) => {
                console.log(`   ${count}x .${cls}`);
            });
    }

    // 7. Quick Fixes vorschlagen
    if (problems.length > 0) {
        console.log('\n🛠️ Schnelltest: Farbe hinzufügen');
        console.log('Kopiere folgenden CSS-Fix in die Developer Tools (Styles Tab):');

        const uniqueClasses = [...new Set(problems.map(p => p.className).filter(Boolean))];
        uniqueClasses.slice(0, 5).forEach(cls => {
            console.log(`.${cls} { color: var(--text-primary) !important; }`);
        });
    }

    return {
        problems,
        count: problems.length,
        clear: () => location.reload()
    };
})();
