/**
 * Client-side filter manager with chip bar and popover dialogs.
 * Adapted from ServerSideFilterManager for client-side DataTables.
 */

function escapeHtml(text) {
    if (!text) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

function formatNumber(value) {
    if (value == null || isNaN(value)) return '';
    return Number(value).toLocaleString();
}

function createModal(options = {}) {
    const overlay = document.createElement('div');
    overlay.className = 'filter-modal';

    const inner = document.createElement('div');
    inner.innerHTML = options.content || '';
    while (inner.firstChild) overlay.appendChild(inner.firstChild);

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal(overlay);
    });

    const escHandler = (e) => {
        if (e.key === 'Escape') {
            closeModal(overlay);
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);

    document.body.appendChild(overlay);
    return overlay;
}

function closeModal(modal) {
    if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
}

function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' toast-error' : ' toast-success');
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

class ClientFilterManager {
    constructor(options) {
        this.columns = options.columns || [];
        this.filterBarId = options.filterBarId || null;
        this.syncURL = options.syncURL !== false;
        this.showCopyLinkButton = options.showCopyLinkButton !== false;
        this.onFilterChange = options.onFilterChange || null;
        this.table = null;
        this.activeFilters = {};
        // Precomputed unique values per column for multiselect
        this._optionsCache = {};

        if (this.syncURL) this._applyFiltersFromURL();
    }

    init(dataTable) {
        this.table = dataTable;
        this._setupFilterBar();
        if (Object.keys(this.activeFilters).length > 0) {
            this._updateFilterBar();
            this._applyToTable();
        }
    }

    setOptions(field, values) {
        this._optionsCache[field] = values;
    }

    // ---- Filter Bar ----

    _setupFilterBar() {
        const filterBar = document.getElementById(this.filterBarId);
        if (!filterBar) return;

        const buttonContainer = document.getElementById('toolbarButtons') || filterBar;

        let addBtn = buttonContainer.querySelector('.add-filter-btn');
        if (!addBtn) {
            addBtn = document.createElement('button');
            addBtn.className = 'add-filter-btn';
            addBtn.textContent = '+ Add Filter';
            buttonContainer.appendChild(addBtn);
        }
        addBtn.addEventListener('click', () => this._openFilterSelection());

        let clearBtn = buttonContainer.querySelector('.clear-filters-btn');
        if (!clearBtn) {
            clearBtn = document.createElement('button');
            clearBtn.className = 'clear-filters-btn';
            clearBtn.textContent = 'Clear All';
            clearBtn.style.display = 'none';
            buttonContainer.appendChild(clearBtn);
            clearBtn.addEventListener('click', () => this.clearAll());
        }

        if (this.syncURL && this.showCopyLinkButton) {
            let copyBtn = buttonContainer.querySelector('.copy-link-btn');
            if (!copyBtn) {
                copyBtn = document.createElement('button');
                copyBtn.className = 'copy-link-btn';
                copyBtn.textContent = 'Copy Link';
                buttonContainer.appendChild(copyBtn);
                copyBtn.addEventListener('click', () => this.copyShareableURL());
            }
        }
    }

    // ---- Filter Selection ----

    _openFilterSelection() {
        const filterableColumns = this.columns.filter(col => col.filterType !== null);
        const optionItems = filterableColumns.map(col =>
            '<label class="filter-option">'
            + '<input type="checkbox" value="' + escapeHtml(col.field) + '" data-name="' + escapeHtml(col.name) + '">'
            + escapeHtml(col.name)
            + '</label>'
        ).join('');

        const content = '<div class="filter-popover">'
            + '<div class="filter-title">Add filter</div>'
            + '<input type="text" class="filter-search filter-options-search" placeholder="Search columns...">'
            + '<div class="filter-options">' + optionItems + '</div></div>';

        const modal = createModal({ content });

        $(modal).find('.filter-options-search').on('input', function () {
            const q = this.value.toLowerCase();
            $(modal).find('.filter-option').each(function () {
                this.style.display = this.textContent.toLowerCase().includes(q) ? '' : 'none';
            });
        }).focus();

        modal.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', () => {
                if (cb.checked) {
                    closeModal(modal);
                    const col = this.columns.find(c => c.field === cb.value);
                    if (col) this._openFilterDialog(col);
                }
            });
        });
    }

    _openFilterDialog(col) {
        if (col.filterType === 'multiselect') this._openMultiselectDialog(col);
        else if (col.filterType === 'text') this._openTextDialog(col);
    }

    // ---- Multiselect ----

    _openMultiselectDialog(col) {
        const values = this._optionsCache[col.field] || [];
        const currentFilter = this.activeFilters[col.field];
        const selectedValues = currentFilter?.values || [];

        const optionItems = values.map(val => {
            const checked = selectedValues.includes(val) ? ' checked' : '';
            return '<label class="filter-option">'
                + '<input type="checkbox" value="' + escapeHtml(val) + '"' + checked + '>'
                + escapeHtml(val)
                + '</label>';
        }).join('');

        const showSearch = values.length > 10;
        const searchHtml = showSearch
            ? '<input type="text" class="filter-search filter-options-search" placeholder="Search...">'
            : '';

        const content = '<div class="filter-popover">'
            + '<div class="filter-title">Filter: ' + escapeHtml(col.name) + '</div>'
            + searchHtml
            + '<div class="filter-options">' + optionItems + '</div>'
            + '<div class="filter-buttons">'
            + '<button class="btn btn-clear">Clear</button>'
            + '<button class="btn btn-apply">Apply</button>'
            + '</div></div>';

        const modal = createModal({ content });
        const $p = $(modal).find('.filter-popover');

        if (showSearch) {
            $p.find('.filter-options-search').on('input', function () {
                const q = this.value.toLowerCase();
                $p.find('.filter-option').each(function () {
                    this.style.display = this.textContent.toLowerCase().includes(q) ? '' : 'none';
                });
            }).focus();
        }

        $p.find('.btn-clear').on('click', () => {
            delete this.activeFilters[col.field];
            this._applyAndRedraw();
            closeModal(modal);
        });

        $p.find('.btn-apply').on('click', () => {
            const checked = [];
            $p.find('input[type="checkbox"]:checked').each(function () {
                checked.push($(this).val());
            });
            if (checked.length > 0) {
                this.activeFilters[col.field] = { type: 'multiselect', values: checked, name: col.name };
            } else {
                delete this.activeFilters[col.field];
            }
            this._applyAndRedraw();
            closeModal(modal);
        });
    }

    // ---- Text ----

    _openTextDialog(col) {
        const currentFilter = this.activeFilters[col.field];
        const currentTerms = currentFilter?.value ? currentFilter.value.split(',').map(t => t.trim()).filter(t => t) : [];

        const content = '<div class="filter-popover">'
            + '<div class="filter-title">Filter: ' + escapeHtml(col.name) + '</div>'
            + '<div class="text-tags-container"></div>'
            + '<input type="text" class="filter-text-input filter-search" placeholder="Type a term and press Enter...">'
            + '<div class="filter-buttons">'
            + '<button class="btn btn-clear">Clear</button>'
            + '<button class="btn btn-apply">Apply</button>'
            + '</div></div>';

        const modal = createModal({ content });
        const $p = $(modal).find('.filter-popover');
        const $input = $p.find('.filter-text-input');
        const $tags = $p.find('.text-tags-container');
        const terms = [...currentTerms];

        function renderTags() {
            $tags.empty();
            terms.forEach((term, i) => {
                const tag = $('<span class="text-tag">')
                    .append($('<span class="text-tag-label">').text(term))
                    .append($('<span class="text-tag-remove">').text('\u00d7').on('click', () => {
                        terms.splice(i, 1);
                        renderTags();
                        $input.focus();
                    }));
                $tags.append(tag);
            });
        }

        renderTags();
        $input.focus();

        $input.on('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const val = $input.val().trim();
                if (val && !terms.includes(val)) { terms.push(val); renderTags(); }
                $input.val('').focus();
            } else if (e.key === 'Backspace' && !$input.val() && terms.length > 0) {
                terms.pop();
                renderTags();
            }
        });

        $p.find('.btn-clear').on('click', () => {
            delete this.activeFilters[col.field];
            this._applyAndRedraw();
            closeModal(modal);
        });

        $p.find('.btn-apply').on('click', () => {
            const val = $input.val().trim();
            if (val && !terms.includes(val)) terms.push(val);
            if (terms.length > 0) {
                this.activeFilters[col.field] = { type: 'text', value: terms.join(','), name: col.name };
            } else {
                delete this.activeFilters[col.field];
            }
            this._applyAndRedraw();
            closeModal(modal);
        });
    }

    // ---- Apply ----

    _applyAndRedraw() {
        this._updateFilterBar();
        if (this.syncURL) this._updateURL();
        this._applyToTable();
        if (this.onFilterChange) this.onFilterChange();
    }

    _applyToTable() {
        if (!this.table) return;

        // Build a custom search function
        const self = this;
        // Remove any previous custom filter
        $.fn.dataTable.ext.search = $.fn.dataTable.ext.search.filter(fn => fn._pmiFilter !== true);

        if (Object.keys(this.activeFilters).length > 0) {
            const filterFn = function (settings, data, dataIndex) {
                for (const [field, filter] of Object.entries(self.activeFilters)) {
                    const col = self.columns.find(c => c.field === field);
                    if (!col) continue;
                    const cellValue = data[col.index] || '';
                    // Strip HTML tags for comparison
                    const cleanValue = cellValue.replace(/<[^>]*>/g, '').trim();

                    if (filter.type === 'multiselect') {
                        if (!filter.values.includes(cleanValue)) return false;
                    } else if (filter.type === 'text') {
                        const terms = filter.value.split(',').map(t => t.trim().toLowerCase());
                        const lower = cleanValue.toLowerCase();
                        if (!terms.some(t => lower.includes(t))) return false;
                    }
                }
                return true;
            };
            filterFn._pmiFilter = true;
            $.fn.dataTable.ext.search.push(filterFn);
        }

        this.table.draw();
    }

    // ---- Filter Chips ----

    _updateFilterBar() {
        const filterBar = document.getElementById(this.filterBarId);
        if (!filterBar) return;

        filterBar.querySelectorAll('.filter-chip.column-filter-chip').forEach(c => c.remove());
        const existingLabel = filterBar.querySelector('.bar-label.filter-label');
        if (existingLabel) existingLabel.remove();

        const hasFilters = Object.keys(this.activeFilters).length > 0;
        const emptyMsg = filterBar.querySelector('.filters-bar-empty');
        if (emptyMsg) emptyMsg.style.display = hasFilters ? 'none' : '';

        const clearBtn = document.querySelector('.clear-filters-btn');
        if (clearBtn) clearBtn.style.display = hasFilters ? '' : 'none';

        if (hasFilters) {
            const label = document.createElement('span');
            label.className = 'bar-label filter-label';
            label.textContent = 'Filtered by:';
            filterBar.insertBefore(label, filterBar.firstChild);

            Object.entries(this.activeFilters).forEach(([field, filter]) => {
                const chip = document.createElement('div');
                chip.className = 'filter-chip column-filter-chip';

                const displayValue = filter.type === 'multiselect'
                    ? filter.values.join(', ')
                    : filter.value;

                const chipLabel = document.createElement('span');
                chipLabel.className = 'filter-chip-label';
                chipLabel.textContent = filter.name + ':';

                const chipValue = document.createElement('span');
                chipValue.className = 'filter-chip-value';
                chipValue.textContent = displayValue;

                const chipRemove = document.createElement('span');
                chipRemove.className = 'filter-chip-remove';
                chipRemove.textContent = '\u00d7';
                chipRemove.addEventListener('click', () => {
                    delete this.activeFilters[field];
                    this._applyAndRedraw();
                });

                const editHandler = () => {
                    const col = this.columns.find(c => c.field === field);
                    if (col) this._openFilterDialog(col);
                };
                chipLabel.style.cursor = 'pointer';
                chipValue.style.cursor = 'pointer';
                chipLabel.addEventListener('click', editHandler);
                chipValue.addEventListener('click', editHandler);

                chip.appendChild(chipLabel);
                chip.appendChild(chipValue);
                chip.appendChild(chipRemove);
                filterBar.appendChild(chip);
            });
        }
    }

    // ---- URL Sync ----

    _updateURL() {
        const url = new URL(window.location);
        url.search = '';
        Object.entries(this.activeFilters).forEach(([field, filter]) => {
            if (filter.type === 'multiselect') {
                url.searchParams.set(field, filter.values.join(','));
            } else {
                url.searchParams.set(field, filter.value);
            }
        });
        window.history.replaceState({}, '', url);
    }

    _applyFiltersFromURL() {
        const params = new URLSearchParams(window.location.search);
        if (params.toString() === '') return;

        const fieldToColumn = {};
        this.columns.forEach(col => { if (col.filterType) fieldToColumn[col.field] = col; });

        params.forEach((value, key) => {
            const col = fieldToColumn[key];
            if (!col) return;
            if (col.filterType === 'multiselect') {
                const values = value.split(',').map(v => v.trim()).filter(v => v);
                if (values.length > 0) {
                    this.activeFilters[col.field] = { type: 'multiselect', values, name: col.name };
                }
            } else if (col.filterType === 'text') {
                if (value) {
                    this.activeFilters[col.field] = { type: 'text', value, name: col.name };
                }
            }
        });
    }

    clearAll() {
        this.activeFilters = {};
        this._applyAndRedraw();
    }

    copyShareableURL() {
        navigator.clipboard.writeText(window.location.href).then(() => {
            showToast('Link copied to clipboard!');
        }).catch(() => {
            showToast('Failed to copy link', true);
        });
    }
}
