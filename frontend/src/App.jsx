import { Route, Routes } from "react-router-dom";

import { Layout, Protected } from "./components/Layout.jsx";
import { LoginPage, RegisterPage } from "./pages/AuthPages.jsx";
import { FeedPage } from "./pages/FeedPage.jsx";
import { FriendsPage } from "./pages/FriendsPage.jsx";
import { PhotoPage } from "./pages/PhotoPage.jsx";
import { ProfilePage } from "./pages/ProfilePage.jsx";
import { UploadPage } from "./pages/UploadPage.jsx";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route
          index
          element={
            <Protected>
              <FeedPage />
            </Protected>
          }
        />
        <Route
          path="search"
          element={
            <Protected>
              <FeedPage searchMode />
            </Protected>
          }
        />
        <Route
          path="upload"
          element={
            <Protected>
              <UploadPage />
            </Protected>
          }
        />
        <Route
          path="photos/:photoId"
          element={
            <Protected>
              <PhotoPage />
            </Protected>
          }
        />
        <Route
          path="friends"
          element={
            <Protected>
              <FriendsPage />
            </Protected>
          }
        />
        <Route
          path="profile"
          element={
            <Protected>
              <ProfilePage />
            </Protected>
          }
        />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="*" element={<p className="empty">That page does not exist.</p>} />
      </Route>
    </Routes>
  );
}
