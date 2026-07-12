import React from 'react';
import { Outlet } from 'react-router-dom';
import { Box } from '@mui/material';
import Sidebar from '../components/layout/Sidebar';
import TopBar from '../components/layout/TopBar';

const MainLayout: React.FC = () => (
  <Box display="flex" minHeight="100vh" bgcolor="background.default">
    <Sidebar />
    <Box display="flex" flexDirection="column" flex={1} sx={{ overflowX: 'hidden', height: "100vh" }}>
      <TopBar />
      <Box component="main" flex={1} sx={{ overflowY: 'auto', p: { xs: 2, sm: 3 } }}>
        <Outlet />
      </Box>
    </Box>
  </Box>
);

export default MainLayout;
