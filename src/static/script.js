const socket = io();

// Function to update the table with new DNS records
function updateTable(records) {
    const tableBody = document.getElementById('records-body');
    tableBody.innerHTML = ''; // Clear existing rows

    records.forEach(record => {
        const row = document.createElement('tr');
        const nameCell = document.createElement('td');
        const rdatasetCell = document.createElement('td');
        const ttlCell = document.createElement('td');

        nameCell.textContent = record.name;
        rdatasetCell.textContent = record.rdataset;
        ttlCell.textContent = record.ttl;

        row.appendChild(nameCell);
        row.appendChild(rdatasetCell);
        row.appendChild(ttlCell);
        tableBody.appendChild(row);
    });
}

// Listen for 'dns_records' event from the server
socket.on('dns_records', (data) => {
    updateTable(data.records);
});