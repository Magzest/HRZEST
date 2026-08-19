import React, { useMemo, useState, useEffect } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  RefreshControl,
  Alert,
  View,
  Text,
  TouchableOpacity,
  Modal,
  TextInput,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import ProfileHeader from "../components/profile/ProfileHeader";
import NotificationHeaderCard from "../components/notifications/NotificationHeaderCard";
import NotificationFilter from "../components/notifications/NotificationFilter";
import NotificationCard from "../components/notifications/NotificationCard";
import NotificationEmpty from "../components/notifications/NotificationEmpty";

import { useAuth } from "../store/AuthContext";
import {
  fetchNotifications,
  fetchEmployeeNotifications,
  markNotificationsRead,
  markEmployeeNotificationsRead,
} from "../api/client";
import { notificationFilters } from "../data/notificationsData";

export default function NotificationsScreen() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [notificationsList, setNotificationsList] = useState([]);
  const [selectedFilter, setSelectedFilter] = useState("All");
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);

  // Broadcast Modal State (Admin)
  const [broadcastVisible, setBroadcastVisible] = useState(false);
  const [broadcastTitle, setBroadcastTitle] = useState("");
  const [broadcastMessage, setBroadcastMessage] = useState("");
  const [broadcasting, setBroadcasting] = useState(false);

  const loadNotifications = async () => {
    try {
      const apiCall = isAdmin ? fetchNotifications : fetchEmployeeNotifications;
      const res = await apiCall();
      if (res?.data?.notifications && Array.isArray(res.data.notifications)) {
        setNotificationsList(res.data.notifications);
      } else if (res?.data?.ok && Array.isArray(res.data.data)) {
        setNotificationsList(res.data.data);
      } else {
        setNotificationsList([]);
      }
    } catch (_) {
      setNotificationsList([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadNotifications();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadNotifications();
  };

  const handleMarkAllRead = async () => {
    try {
      if (isAdmin) {
        await markNotificationsRead();
      } else {
        await markEmployeeNotificationsRead();
      }
    } catch (_) {}
    setNotificationsList((prev) =>
      prev.map((item) => ({ ...item, unread: false }))
    );
    Alert.alert("Success", "All notifications marked as read.");
  };

  const handleSendBroadcast = async () => {
    // No broadcast endpoint exists anywhere in the backend -- not a Bearer
    // API, not even a session-based web route -- so this call was always
    // guaranteed to fail, and the old catch block claimed success anyway
    // ("Announcement Queued... broadcasted locally") on every single
    // attempt. Staying honest about this instead.
    Alert.alert(
      "Not Available Yet",
      "Broadcasting an announcement to all staff isn't implemented yet on either web or mobile."
    );
  };

  const filteredNotifications = useMemo(() => {
    switch (selectedFilter) {
      case "Unread":
        return notificationsList.filter((item) => item.unread);
      case "HR":
        return notificationsList.filter((item) => item.type === "HR");
      case "Attendance":
        return notificationsList.filter((item) => item.type === "Attendance");
      case "Leave":
        return notificationsList.filter((item) => item.type === "Leave");
      default:
        return notificationsList;
    }
  }, [selectedFilter, notificationsList]);

  const unreadCount = notificationsList.filter((item) => item.unread).length;

  const handleNotificationPress = (notification) => {
    Alert.alert(notification.title, notification.message);
  };

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Alerts & Announcements" showBack={false} />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={["#173B8C"]}
            tintColor="#173B8C"
          />
        }
      >
        <NotificationHeaderCard total={notificationsList.length} unread={unreadCount} />

        {/* Action Row */}
        <View style={styles.actionRow}>
          {unreadCount > 0 && (
            <TouchableOpacity style={styles.markReadBtn} onPress={handleMarkAllRead}>
              <Ionicons name="checkmark-done" size={16} color="#0284C7" style={{ marginRight: 4 }} />
              <Text style={styles.markReadText}>Mark all as read</Text>
            </TouchableOpacity>
          )}

          {isAdmin && (
            <TouchableOpacity style={styles.broadcastBtn} onPress={() => setBroadcastVisible(true)}>
              <Ionicons name="mega-phone-outline" size={16} color="#FFFFFF" style={{ marginRight: 6 }} />
              <Text style={styles.broadcastBtnText}>Send Broadcast</Text>
            </TouchableOpacity>
          )}
        </View>

        <NotificationFilter
          filters={notificationFilters}
          selectedFilter={selectedFilter}
          onSelectFilter={setSelectedFilter}
        />

        {loading ? (
          <ActivityIndicator size="large" color="#173B8C" style={{ marginVertical: 30 }} />
        ) : filteredNotifications.length > 0 ? (
          filteredNotifications.map((notification) => (
            <NotificationCard
              key={notification.id}
              notification={notification}
              onPress={handleNotificationPress}
            />
          ))
        ) : (
          <NotificationEmpty />
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Admin Broadcast Modal */}
      <Modal visible={broadcastVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Ionicons name="megaphone" size={22} color="#0B2253" style={{ marginRight: 8 }} />
              <Text style={styles.modalTitle}>Broadcast Announcement</Text>
            </View>

            <Text style={styles.inputLabel}>Announcement Title</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Office Holiday Notice / Townhall"
              value={broadcastTitle}
              onChangeText={setBroadcastTitle}
            />

            <Text style={styles.inputLabel}>Message Content</Text>
            <TextInput
              style={[styles.input, { minHeight: 90, textAlignVertical: "top" }]}
              multiline
              placeholder="Enter announcement details for all employees..."
              value={broadcastMessage}
              onChangeText={setBroadcastMessage}
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setBroadcastVisible(false)}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.submitBtn}
                disabled={broadcasting}
                onPress={handleSendBroadcast}
              >
                {broadcasting ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.submitBtnText}>Broadcast Now</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F5F7FB",
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 30,
  },
  actionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  markReadBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#E0F2FE",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
  },
  markReadText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#0284C7",
  },
  broadcastBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#0B2253",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 14,
    marginLeft: "auto",
  },
  broadcastBtnText: {
    fontSize: 13,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 20,
  },
  modalContent: {
    width: "100%",
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 20,
    elevation: 8,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: "#475569",
    marginBottom: 6,
  },
  input: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: "#0F172A",
    marginBottom: 14,
  },
  modalBtnRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 8,
  },
  cancelBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "#F1F5F9",
  },
  cancelBtnText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#64748B",
  },
  submitBtn: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "#0B2253",
  },
  submitBtnText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
  },
});

