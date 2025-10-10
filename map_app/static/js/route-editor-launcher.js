(function() {
    function resolveProjectQuery() {
        let search = '';
        try {
            if (window.currentProjectId) {
                search = '?projectId=' + encodeURIComponent(window.currentProjectId);
            }
        } catch (e) {
            // ignore
        }
        if (!search) {
            const locSearch = window.location && window.location.search ? window.location.search : '';
            if (locSearch && locSearch.length > 1) {
                search = locSearch;
            }
        }
        if (!search) {
            try {
                const match = document.cookie.match(/(?:^|; )projectId=([^;]+)/);
                if (match && match[1]) {
                    search = '?projectId=' + encodeURIComponent(match[1]);
                }
            } catch (e) {
                // ignore
            }
        }
        return search;
    }

    window.openRouteEditor = function openRouteEditor() {
        const query = resolveProjectQuery();
        const url = '/route-editor' + (query || '');
        window.open(url, '_blank', 'width=1400,height=900');
    };
})();
