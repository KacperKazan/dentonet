// handle sorting by date
function sortTable(n, tableId) {
    let table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
    table = document.getElementById(tableId);
    switching = true;
    dir = "asc";
    while (switching) {
      switching = false;
      rows = table.rows;
      for (i = 1; i < (rows.length - 1); i++) {
        shouldSwitch = false;
        x = rows[i].getElementsByTagName("td")[n];
        y = rows[i + 1].getElementsByTagName("td")[n];
        if (dir == "asc") {
          if (x.innerHTML.toLowerCase() > y.innerHTML.toLowerCase()) {
            shouldSwitch = true;
            break;
          }
        } else if (dir == "desc") {
          if (x.innerHTML.toLowerCase() < y.innerHTML.toLowerCase()) {
            shouldSwitch = true;
            break;
          }
        }
      }
      if (shouldSwitch) {
        rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
        switching = true;
        switchcount++;
      } else {
        if (switchcount == 0 && dir == "asc") {
          dir = "desc";
          switching = true;
        }
      }
    }
  }
  
  // handle pagination
  function paginate(tableId, rowsPerPage) {
    let table, rows, numOfPages, currentPage;
    table = document.getElementById(tableId);
    rows = table.rows;
    numOfPages = Math.ceil(rows.length / rowsPerPage);
    currentPage = 1;
    document.getElementById("page-number").innerHTML = "Page " + currentPage + " of " + numOfPages;
    for (let i = rowsPerPage; i < rows.length; i++) {
      rows[i].style.display = "none";
    }
    document.getElementById("prev-page").addEventListener("click", function() {
      if (currentPage > 1) {
        currentPage--;
        document.getElementById("page-number").innerHTML = "Page " + currentPage + " of " + numOfPages;
        for (let i = (currentPage-1)*rowsPerPage; i < currentPage*rowsPerPage; i++) {
          rows[i].style.display = "";
        }
        for (let i = currentPage*rowsPerPage; i < rows.length; i++) {
          rows[i].style.display = "none";
        }
      }
    });
    document.getElementById("next-page").addEventListener("click", function() {
      if (currentPage < numOfPages) {
        currentPage++;
        document.getElementById("page-number").innerHTML = "Page " + currentPage + " of " + numOfPages;
        for (let i = (currentPage-1)*rowsPerPage; i < currentPage*rowsPerPage; i++) {
          rows[i].style.display = "";
        }
        for (let i = (currentPage-1)*rowsPerPage-1; i >= 0; i--) {
          rows[i].style.display = "none";
        }
      }
    });
  }