import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  StatusBar,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useNavigation, DrawerActions } from "@react-navigation/native";

export default function AdminHeader({
  title = "Dashboard",
  subtitle = "ADMIN PORTAL",
  profileImage,
  notificationCount = 3,
  onMenu,
  onNotification,
  onProfile,
}) {
  const navigation = useNavigation();

  const handleMenuPress = () => {
    if (typeof onMenu === "function") {
      try {
        onMenu();
      } catch (e) {
        navigation.dispatch(DrawerActions.openDrawer());
      }
    } else {
      navigation.dispatch(DrawerActions.openDrawer());
    }
  };

  const handleProfilePress = () => {
    if (typeof onProfile === "function") {
      onProfile();
    } else {
      try {
        navigation.navigate("Settings", { tab: "profile" });
      } catch (e) {
        // Fallback if settings route not found
      }
    }
  };

  return (
    <>
      <StatusBar
        translucent
        backgroundColor="transparent"
        barStyle="dark-content"
      />
      <View style={styles.container}>
        {/* Hamburger Menu Button */}
        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.iconButton}
          onPress={handleMenuPress}
        >
          <Ionicons
            name="menu-sharp"
            size={22}
            color="#0F172A"
          />
        </TouchableOpacity>

        {/* Header Title Section (Aligned next to Hamburger) */}
        <View style={styles.titleSection}>
          {!!subtitle && (
            <View style={styles.tagBadge}>
              <Text style={styles.tagText}>{subtitle.toUpperCase()}</Text>
            </View>
          )}
          <Text numberOfLines={1} style={styles.title}>
            {title}
          </Text>
        </View>

        {/* Right Action Icons */}
        <View style={styles.rightGroup}>
          {onNotification && (
            <TouchableOpacity
              activeOpacity={0.7}
              style={styles.iconButton}
              onPress={onNotification}
            >
              <Ionicons
                name="notifications-outline"
                size={20}
                color="#0F172A"
              />
              {notificationCount > 0 && (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>
                    {notificationCount > 9 ? "9+" : notificationCount}
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          )}

          <TouchableOpacity
            activeOpacity={0.8}
            style={styles.avatarButton}
            onPress={handleProfilePress}
          >
            {profileImage ? (
              <Image
                source={{ uri: profileImage }}
                style={styles.avatarImage}
              />
            ) : (
              <View style={styles.avatarFallback}>
                <Ionicons
                  name="person-sharp"
                  size={18}
                  color="#2563EB"
                />
              </View>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: Platform.OS === "ios" ? 54 : (StatusBar.currentHeight || 24) + 12,
    paddingBottom: 14,
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
    shadowColor: "#0F172A",
    shadowOpacity: 0.03,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#F8FAFC",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  titleSection: {
    flex: 1,
    marginLeft: 12,
    marginRight: 8,
    justifyContent: "center",
  },
  tagBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#EFF6FF",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    marginBottom: 2,
  },
  tagText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#2563EB",
    letterSpacing: 0.8,
  },
  title: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.3,
  },
  rightGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  badge: {
    position: "absolute",
    top: 5,
    right: 5,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: "#EF4444",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 4,
    borderWidth: 1.5,
    borderColor: "#FFFFFF",
  },
  badgeText: {
    color: "#FFFFFF",
    fontSize: 9,
    fontWeight: "800",
  },
  avatarButton: {
    borderRadius: 12,
    overflow: "hidden",
  },
  avatarImage: {
    width: 40,
    height: 40,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: "#E2E8F0",
  },
  avatarFallback: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#EFF6FF",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1.5,
    borderColor: "#DBEAFE",
  },
});