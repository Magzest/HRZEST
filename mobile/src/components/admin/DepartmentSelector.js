import React from "react";

import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function DepartmentSelector({
  departments = [],
  selectedDepartment,
  onPress,
}) {
  return (
    <View style={styles.container}>

      {/* Header */}

      <View style={styles.header}>

        <Text style={styles.title}>
          Department
        </Text>

        <Text style={styles.subtitle}>
          Filter Performance Reviews
        </Text>

      </View>

      {/* Selector */}

      <TouchableOpacity
        activeOpacity={0.9}
        style={styles.selector}
        onPress={onPress}
      >

        <View style={styles.leftSection}>

          <View style={styles.iconContainer}>

            <Ionicons
              name="business-outline"
              size={22}
              color={PERFORMANCE_THEME.colors.primary}
            />

          </View>

          <View style={styles.textContainer}>

            <Text style={styles.label}>
              Selected Department
            </Text>

            <Text
              numberOfLines={1}
              style={styles.value}
            >
              {selectedDepartment ||
                departments[0] ||
                "All Departments"}
            </Text>

          </View>

        </View>

        <View style={styles.arrowContainer}>

          <Ionicons
            name="chevron-down"
            size={22}
            color={PERFORMANCE_THEME.colors.textMuted}
          />

        </View>

      </TouchableOpacity>

    </View>
  );
}

const styles = StyleSheet.create({

  container: {
    marginBottom: 24,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginBottom: 14,
  },

  title: {
    fontSize: 17,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  subtitle: {
    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  selector: {
    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    paddingHorizontal: 18,

    paddingVertical: 18,

    borderWidth: 1,

    borderColor:
      PERFORMANCE_THEME.colors.border,

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    shadowColor: "#0F172A",

    shadowOpacity: 0.05,

    shadowRadius: 14,

    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 5,
  },

  leftSection: {
    flexDirection: "row",

    alignItems: "center",

    flex: 1,
  },

  iconContainer: {
    width: 54,

    height: 54,

    borderRadius: 18,

    backgroundColor:
      PERFORMANCE_THEME.colors.primaryLight,

    justifyContent: "center",

    alignItems: "center",

    marginRight: 16,
  },

  textContainer: {
    flex: 1,
  },

  label: {
    fontSize: 12,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  value: {
    marginTop: 4,

    fontSize: 16,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  arrowContainer: {
    width: 42,

    height: 42,

    borderRadius: 14,

    backgroundColor: "#F8FAFC",

    justifyContent: "center",

    alignItems: "center",
  },

});