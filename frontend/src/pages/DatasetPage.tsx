/**
 * pages/DatasetPage.tsx
 * =====================
 * Predefined US Tax & Legal Document Registry page.
 *
 * Displays:
 *   - Tabulated list of all 100 documents
 *   - Search and category filters (All, Acts, Court Judgements, Tax, Opinions)
 *   - Sorting by columns (Name, Category, Pages, Status)
 *   - Paginated display with easy navigation
 *   - Direct click-to-open links routing to the Document Viewer
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  TextField,
  Tabs,
  Tab,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  TableSortLabel,
  Chip,
  IconButton,
  Tooltip,
  InputAdornment,
  CircularProgress,
} from "@mui/material";
import {
  Search as SearchIcon,
  Visibility as OpenIcon,
  Description as FileIcon,
} from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import { documentService } from "../services/documentService";
import type { DocumentListItem } from "../types/document.types";

type Order = "asc" | "desc";
type OrderableKeys = "file_name" | "category" | "page_count" | "status";

const DatasetPage: React.FC = () => {
  const navigate = useNavigate();

  // Search, filter, sorting, and pagination states
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [order, setOrder] = useState<Order>("asc");
  const [orderBy, setOrderBy] = useState<OrderableKeys>("file_name");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Tab definitions
  const categories = ["All", "Acts", "CourtJudgement", "Tax", "Legal_opinion"];
  const categoryLabels: Record<string, string> = {
    All: "All Categories",
    Acts: "Acts & Statutes",
    CourtJudgement: "Court Judgments",
    Tax: "Tax Documents",
    Legal_opinion: "Legal Opinions",
  };

  // Query: fetch filtered list of documents from client-side service
  const { data, isLoading } = useQuery({
    queryKey: ["documents", activeTab, searchQuery, statusFilter],
    queryFn: () => documentService.listDocuments(activeTab, searchQuery, statusFilter),
  });

  const handleTabChange = (_: React.SyntheticEvent, newValue: string) => {
    setActiveTab(newValue);
    setPage(0);
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setPage(0);
  };

  const handleRequestSort = (property: OrderableKeys) => {
    const isAsc = orderBy === property && order === "asc";
    setOrder(isAsc ? "desc" : "asc");
    setOrderBy(property);
  };

  const handlePageChange = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleRowsPerPageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleOpenDocument = (doc: DocumentListItem) => {
    // Navigate to viewer page with query parameters
    navigate(`/viewer?document=${encodeURIComponent(doc.file_name)}&category=${encodeURIComponent(doc.category)}&page=1`);
  };

  // Client-side sorting logic
  const sortData = (list: DocumentListItem[]): DocumentListItem[] => {
    return [...list].sort((a, b) => {
      let aVal: any = a[orderBy];
      let bVal: any = b[orderBy];

      // Safe check for undefined values
      if (aVal === undefined) aVal = "";
      if (bVal === undefined) bVal = "";

      if (typeof aVal === "string") {
        return order === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      } else {
        return order === "asc" ? aVal - bVal : bVal - aVal;
      }
    });
  };

  const filteredDocs = data?.documents ?? [];
  const sortedDocs = sortData(filteredDocs);
  const paginatedDocs = sortedDocs.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  const getStatusChip = (status: string) => {
    switch (status) {
      case "valid":
        return <Chip label="Valid" color="success" size="small" variant="outlined" sx={{ fontWeight: 600 }} />;
      case "duplicate":
        return <Chip label="Duplicate" color="warning" size="small" variant="outlined" sx={{ fontWeight: 600 }} />;
      case "invalid":
        return <Chip label="Corrupted" color="error" size="small" variant="outlined" sx={{ fontWeight: 600 }} />;
      default:
        return <Chip label={status} size="small" variant="outlined" />;
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = 2;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  };

  return (
    <Box>
      <Box mb={3}>
        <Typography variant="h4" fontWeight={700} sx={{ letterSpacing: "-0.03em", mb: 0.5 }}>
          Document Registry
        </Typography>
        <Typography color="text.secondary" variant="body2">
          Pre-indexed knowledge base dataset consisting of 100 federal tax codes, legal opinions, and judicial records.
        </Typography>
      </Box>

      {/* Tabs Filter */}
      <Paper sx={{ mb: 3, borderRadius: 2 }} elevation={1}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            px: 2,
            borderBottom: 1,
            borderColor: "divider",
            "& .MuiTab-root": {
              fontWeight: 600,
              fontSize: "0.9rem",
              py: 2,
            },
          }}
        >
          {categories.map((cat) => (
            <Tab key={cat} label={categoryLabels[cat]} value={cat} />
          ))}
        </Tabs>

        {/* Search controls */}
        <Box p={2} display="flex" gap={2} alignItems="center" flexWrap="wrap">
          <TextField
            placeholder="Search documents by filename or title..."
            value={searchQuery}
            onChange={handleSearchChange}
            size="small"
            variant="outlined"
            sx={{ flexGrow: 1, maxWidth: 500 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon color="action" />
                </InputAdornment>
              ),
            }}
          />

          <Tabs
            value={statusFilter}
            onChange={(_, val) => { setStatusFilter(val); setPage(0); }}
            textColor="secondary"
            indicatorColor="secondary"
            sx={{
              minHeight: 32,
              "& .MuiTab-root": {
                minHeight: 32,
                py: 0.5,
                px: 2,
                fontSize: "0.8rem",
                fontWeight: 600,
              },
            }}
          >
            <Tab label="All Statuses" value="All" />
            <Tab label="Valid Only" value="Valid" />
            <Tab label="Duplicates" value="Duplicate" />
          </Tabs>
        </Box>
      </Paper>

      {/* Document Listing Table */}
      <TableContainer component={Paper} sx={{ borderRadius: 2 }} elevation={1}>
        {isLoading ? (
          <Box display="flex" justifyContent="center" py={10}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell />
                  <TableCell>
                    <TableSortLabel
                      active={orderBy === "file_name"}
                      direction={orderBy === "file_name" ? order : "asc"}
                      onClick={() => handleRequestSort("file_name")}
                    >
                      Document Name
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={orderBy === "category"}
                      direction={orderBy === "category" ? order : "asc"}
                      onClick={() => handleRequestSort("category")}
                    >
                      Category
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right">
                    <TableSortLabel
                      active={orderBy === "page_count"}
                      direction={orderBy === "page_count" ? order : "asc"}
                      onClick={() => handleRequestSort("page_count")}
                    >
                      Page Count
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right">File Size</TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={orderBy === "status"}
                      direction={orderBy === "status" ? order : "asc"}
                      onClick={() => handleRequestSort("status")}
                    >
                      Index Status
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="center">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginatedDocs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                      <Typography variant="body2" color="text.secondary">
                        No documents match the search criteria.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedDocs.map((doc) => (
                    <TableRow
                      key={doc.document_id}
                      hover
                      sx={{
                        cursor: "pointer",
                        "&:last-child td, &:last-child th": { border: 0 },
                      }}
                      onClick={() => handleOpenDocument(doc)}
                    >
                      <TableCell align="center" onClick={(e) => e.stopPropagation()} sx={{ width: 50 }}>
                        <FileIcon color="action" />
                      </TableCell>
                      <TableCell sx={{ fontWeight: 600, color: "text.primary" }}>
                        {doc.file_name}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={categoryLabels[doc.category] || doc.category}
                          size="small"
                          sx={{ fontSize: "0.75rem", fontWeight: 500 }}
                        />
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600 }}>
                        {doc.page_count}
                      </TableCell>
                      <TableCell align="right" color="text.secondary">
                        {formatBytes(doc.file_size_bytes)}
                      </TableCell>
                      <TableCell>{getStatusChip(doc.status)}</TableCell>
                      <TableCell align="center" onClick={(e) => e.stopPropagation()}>
                        <Tooltip title="Open in Reader">
                          <IconButton onClick={() => handleOpenDocument(doc)} color="primary" size="small">
                            <OpenIcon />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
            <TablePagination
              rowsPerPageOptions={[5, 10, 25, 50]}
              component="div"
              count={filteredDocs.length}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={handlePageChange}
              onRowsPerPageChange={handleRowsPerPageChange}
            />
          </>
        )}
      </TableContainer>
    </Box>
  );
};

export default DatasetPage;
