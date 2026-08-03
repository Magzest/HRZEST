import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";
import THEME from "../../constants/theme";

const ACTIONS = [
  {
    title: "Add Employee",
    icon: "person-add",
    color: "#2563EB",
    background: "#DBEAFE",
    screen: "Employees",
  },
  {
    title: "Attendance",
    icon: "calendar",
    color: "#10B981",
    background: "#DCFCE7",
    screen: "Attendance",
  },
  {
    title: "Payroll",
    icon: "wallet",
    color: "#7C3AED",
    background: "#EDE9FE",
    screen: "Payroll",
  },
  {
    title: "Leave",
    icon: "document-text",
    color: "#F59E0B",
    background: "#FEF3C7",
    screen: "LeaveRequests",
  },
];

export default function QuickActionGrid({
  navigation,
}) {
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>
        Quick Actions
      </Text>

      <View style={styles.grid}>
        {ACTIONS.map((item) => (
          <TouchableOpacity
            key={item.title}
            activeOpacity={0.85}
            style={styles.card}
            onPress={() => {
              if (navigation) {
                navigation.navigate(item.screen);
              }
            }}
          >
            <View
              style={[
                styles.iconContainer,
                {
                  backgroundColor:
                    item.background,
                },
              ]}
            >
              <Ionicons
                name={item.icon}
                size={28}
                color={item.color}
              />
            </View>

            <Text
              numberOfLines={2}
              style={styles.title}
            >
              {item.title}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 26,
  },

  heading: {
    fontSize: 22,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 18,
  },

  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
  },

  card: {
    width: "48%",

    backgroundColor: "#FFFFFF",

    borderRadius: 24,

    paddingVertical: 22,

    alignItems: "center",

    marginBottom: 16,

    borderWidth: 1,

    borderColor: "#E8EDF5",

    shadowColor: "#000",

    shadowOpacity: 0.05,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 4,
  },

  iconContainer: {
    width: 64,

    height: 64,

    borderRadius: 20,

    justifyContent: "center",

    alignItems: "center",

    marginBottom: 14,
  },

  title: {
    fontSize: 15,

    fontWeight: "700",

    color: "#0F172A",

    textAlign: "center",

    paddingHorizontal: 8,
  },
});