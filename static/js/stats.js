function showViewStats(shortId) {
    var modalEl = document.getElementById('viewStatsModal');
    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
    document.getElementById('viewStatsBody').innerHTML = '<tr><td colspan="4" class="text-center">加载中...</td></tr>';
    
    fetch('/api/view_stats/' + shortId)
        .then(response => response.json())
        .then(data => {
            var html = '';
            if (data.stats.length === 0) {
                html = '<tr><td colspan="4" class="text-center">暂无浏览记录</td></tr>';
            } else {
                data.stats.forEach(item => {
                    html += `<tr>
                        <td>${item.account}</td>
                        <td>${item.ip || '-'}</td>
                        <td>${item.count}</td>
                        <td>${item.last_viewed}</td>
                    </tr>`;
                });
            }
            document.getElementById('viewStatsBody').innerHTML = html;
        })
        .catch(err => {
            document.getElementById('viewStatsBody').innerHTML = '<tr><td colspan="4" class="text-center text-danger">加载失败</td></tr>';
        });
}
