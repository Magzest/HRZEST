import React from "react";
import {
  View,
  Text,
  StyleSheet,
  Image,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

export default function DashboardHeroCard({
  adminName = "Administrator",
  company = "Workforce Portal",
  totalEmployees = 0,
  present = 0,
  attendance = "0%",
  payroll = "₹0",
  profileImage,
}) {

  return (

    <LinearGradient
      colors={["#0F2460", "#1A3A8F"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.container}
    >

      <View style={styles.topRow}>

        <View style={{ flex: 1 }}>

          <Text style={styles.small}>
            Welcome Back 👋
          </Text>

          <Text
            numberOfLines={1}
            style={styles.name}
          >
            {adminName}
          </Text>

          <Text
            numberOfLines={1}
            style={styles.company}
          >
            {company}
          </Text>

          <View style={styles.dateRow}>

            <Ionicons
              name="calendar-outline"
              size={14}
              color="rgba(255,255,255,.9)"
            />

            <Text style={styles.date}>
              {new Date().toLocaleDateString(
                "en-US",
                {
                  weekday: "long",
                  month: "long",
                  day: "numeric",
                }
              )}
            </Text>

          </View>

        </View>

        {profileImage ? (

          <Image
            source={{
              uri: profileImage,
            }}
            style={styles.avatar}
          />

        ) : (
          <View style={[styles.avatarPlaceholder, { backgroundColor: "rgba(255,255,255,0.2)", borderWidth: 1, borderColor: "rgba(255,255,255,0.4)" }]}>
            <Text style={{ color: "#FFFFFF", fontWeight: "900", fontSize: 24 }}>
              {(company || adminName || "A").charAt(0).toUpperCase()}
            </Text>
          </View>
        )}

      </View>

      <View style={styles.divider} />

      <View style={styles.statsRow}>

        <View style={styles.stat}>

          <Text style={styles.value}>
            {totalEmployees}
          </Text>

          <Text style={styles.label}>
            Employees
          </Text>

        </View>

        <View style={styles.separator} />

        <View style={styles.stat}>

          <Text style={styles.value}>
            {present}
          </Text>

          <Text style={styles.label}>
            Present
          </Text>

        </View>

        <View style={styles.separator} />

        <View style={styles.stat}>

          <Text style={styles.value}>
            {attendance}
          </Text>

          <Text style={styles.label}>
            Attendance
          </Text>

        </View>

        <View style={styles.separator} />

        <View style={styles.stat}>

          <Text style={styles.value}>
            {payroll}
          </Text>

          <Text style={styles.label}>
            Payroll
          </Text>

        </View>

      </View>

    </LinearGradient>

  );

}

const styles = StyleSheet.create({

  container: {

    borderRadius: 28,

    padding: 22,

    marginBottom: 24,

    shadowColor: "#2563EB",

    shadowOpacity: 0.25,

    shadowRadius: 18,

    shadowOffset: {
      width: 0,
      height: 10,
    },

    elevation: 12,

  },

  topRow: {

    flexDirection: "row",

    alignItems: "center",

  },

  small: {

    color: "rgba(255,255,255,.9)",

    fontSize: 13,

    fontWeight: "600",

  },

  name: {

    marginTop: 6,

    fontSize: 28,

    fontWeight: "800",

    color: "#FFFFFF",

  },

  company: {

    marginTop: 4,

    color: "rgba(255,255,255,.85)",

    fontSize: 14,

  },

  dateRow: {

    flexDirection: "row",

    alignItems: "center",

    marginTop: 14,

  },

  date: {

    color: "#FFFFFF",

    marginLeft: 6,

    fontSize: 13,

    fontWeight: "600",

  },

  avatar: {

    width: 72,

    height: 72,

    borderRadius: 36,

    borderWidth: 3,

    borderColor: "#FFFFFF",

  },

  avatarPlaceholder: {

    width: 72,

    height: 72,

    borderRadius: 36,

    backgroundColor: "rgba(255,255,255,.2)",

    justifyContent: "center",

    alignItems: "center",

  },

  divider: {

    height: 1,

    backgroundColor: "rgba(255,255,255,.2)",

    marginVertical: 20,

  },

  statsRow: {

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

  },

  stat: {

    flex: 1,

    alignItems: "center",

  },

  value: {

    color: "#FFFFFF",

    fontSize: 22,

    fontWeight: "800",

  },

  label: {

    marginTop: 5,

    color: "rgba(255,255,255,.9)",

    fontSize: 12,

    fontWeight: "600",

  },

  separator: {

    width: 1,

    height: 36,

    backgroundColor: "rgba(255,255,255,.25)",

  },

});