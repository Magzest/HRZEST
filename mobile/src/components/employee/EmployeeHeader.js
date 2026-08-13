import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../store/AuthContext";

export default function EmployeeHeader({
  employeeName = "John Doe",
  designation = "Software Engineer",
  employeeId = "EMP001",
  date = "",
  profileImage,
  onLogout,
}) {
  const { user } = useAuth();
  const companyName = user?.company || "Organisation Portal";
  const logoUri = user?.logo;

  const hour = new Date().getHours();

  let greeting = "Good Evening";

  if (hour < 12) greeting = "Good Morning";
  else if (hour < 17) greeting = "Good Afternoon";

  return (

    <View style={styles.container}>

      {/* Header */}

      <View style={styles.topRow}>

        <View style={styles.leftSection}>

          <View style={styles.avatarWrapper}>

            {profileImage ? (

              <Image
                source={{ uri: profileImage }}
                style={styles.avatar}
              />

            ) : (

              <View style={styles.placeholder}>

                <Ionicons
                  name="person"
                  size={28}
                  color="#173B8C"
                />

              </View>

            )}

            <View style={styles.onlineDot} />

          </View>

          <View style={styles.info}>
            <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 2 }}>
              {logoUri ? (
                <Image source={{ uri: logoUri }} style={{ width: 14, height: 14, borderRadius: 7, marginRight: 4, backgroundColor: "#FFFFFF" }} />
              ) : (
                <Ionicons name="business" size={12} color="#173B8C" style={{ marginRight: 4 }} />
              )}
              <Text style={{ fontSize: 11, fontWeight: "800", color: "#173B8C", textTransform: "uppercase" }} numberOfLines={1}>
                {companyName}
              </Text>
            </View>

            <Text style={styles.greeting}>
              {greeting}
            </Text>

            <Text
              style={styles.name}
              numberOfLines={1}
            >
              {employeeName}
            </Text>

            <Text
              style={styles.designation}
              numberOfLines={1}
            >
              {designation}
            </Text>

          </View>

        </View>

        <TouchableOpacity
          activeOpacity={0.85}
          onPress={onLogout}
          style={styles.logout}
        >

          <Ionicons
            name="log-out-outline"
            size={22}
            color="#173B8C"
          />

        </TouchableOpacity>

      </View>

      {/* Bottom */}

      <View style={styles.bottomRow}>

        <View style={styles.employeeBadge}>

          <Ionicons
            name="card-outline"
            size={14}
            color="#173B8C"
          />

          <Text style={styles.employeeText}>
            {employeeId}
          </Text>

        </View>

        <View style={styles.dateBadge}>

          <Ionicons
            name="calendar-outline"
            size={14}
            color="#64748B"
          />

          <Text style={styles.dateText}>
            {date}
          </Text>

        </View>

      </View>

    </View>

  );

}

const styles = StyleSheet.create({

  container: {

    backgroundColor: "#FFFFFF",

    borderRadius: 24,

    padding: 20,

    marginBottom: 22,

    borderWidth: 1,

    borderColor: "#E8EDF5",

    shadowColor: "#0F172A",

    shadowOpacity: 0.05,

    shadowRadius: 14,

    shadowOffset: {

      width: 0,

      height: 6,

    },

    elevation: 5,

  },

  topRow: {

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

  },

  leftSection: {

    flexDirection: "row",

    alignItems: "center",

    flex: 1,

  },

  avatarWrapper: {

    position: "relative",

    marginRight: 16,

  },

  avatar: {

    width: 64,

    height: 64,

    borderRadius: 32,

  },

  placeholder: {

    width: 64,

    height: 64,

    borderRadius: 32,

    backgroundColor: "#EEF4FF",

    justifyContent: "center",

    alignItems: "center",

  },

  onlineDot: {

    position: "absolute",

    right: 3,

    bottom: 3,

    width: 14,

    height: 14,

    borderRadius: 7,

    backgroundColor: "#22C55E",

    borderWidth: 3,

    borderColor: "#FFFFFF",

  },

  info: {

    flex: 1,

  },

  greeting: {

    fontSize: 12,

    color: "#64748B",

    fontWeight: "600",

  },

  name: {

    marginTop: 3,

    fontSize: 18,

    fontWeight: "800",

    color: "#0F172A",

    letterSpacing: -0.4,

  },

  designation: {

    marginTop: 3,

    fontSize: 12,

    color: "#64748B",

    fontWeight: "500",

  },

  logout: {

    width: 46,

    height: 46,

    borderRadius: 14,

    justifyContent: "center",

    alignItems: "center",

    backgroundColor: "#F8FAFC",

    borderWidth: 1,

    borderColor: "#E5E7EB",

  },

  bottomRow: {

    marginTop: 20,

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    borderTopWidth: 1,

    borderTopColor: "#EEF2F7",

    paddingTop: 16,

  },

  employeeBadge: {

    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "#EEF4FF",

    paddingHorizontal: 12,

    paddingVertical: 8,

    borderRadius: 18,

  },

  employeeText: {

    marginLeft: 6,

    fontSize: 12,

    fontWeight: "700",

    color: "#173B8C",

  },

  dateBadge: {

    flexDirection: "row",

    alignItems: "center",

  },

  dateText: {

    marginLeft: 6,

    fontSize: 12,

    color: "#64748B",

    fontWeight: "600",

  },

});