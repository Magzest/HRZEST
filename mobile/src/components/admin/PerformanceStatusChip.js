import React from "react";

import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function PerformanceStatusChip({
  status,
}) {

  const STATUS = {

    Completed: {
      icon: "checkmark-circle",

      color:
        PERFORMANCE_THEME.colors.success,

      background:
        PERFORMANCE_THEME.colors.successLight,

      text: "Completed",
    },

    Pending: {
      icon: "time",

      color:
        PERFORMANCE_THEME.colors.warning,

      background:
        PERFORMANCE_THEME.colors.warningLight,

      text: "Pending",
    },

    "Not Started": {
      icon: "ellipse-outline",

      color:
        PERFORMANCE_THEME.colors.textMuted,

      background: "#F1F5F9",

      text: "Not Started",
    },

    "In Review": {
      icon: "eye",

      color:
        PERFORMANCE_THEME.colors.primary,

      background:
        PERFORMANCE_THEME.colors.primaryLight,

      text: "In Review",
    },

    Approved: {
      icon: "shield-checkmark",

      color:
        PERFORMANCE_THEME.colors.success,

      background:
        PERFORMANCE_THEME.colors.successLight,

      text: "Approved",
    },

    Rejected: {
      icon: "close-circle",

      color:
        PERFORMANCE_THEME.colors.danger,

      background:
        PERFORMANCE_THEME.colors.dangerLight,

      text: "Rejected",
    },

  };

  const config =
    STATUS[status] ||
    STATUS["Pending"];

  return (

    <View
      style={[
        styles.container,
        {
          backgroundColor:
            config.background,
        },
      ]}
    >

      <Ionicons
        name={config.icon}
        size={15}
        color={config.color}
      />

      <Text
        style={[
          styles.text,
          {
            color: config.color,
          },
        ]}
      >
        {config.text}
      </Text>

    </View>

  );

}

const styles = StyleSheet.create({

  container: {

    flexDirection: "row",

    alignItems: "center",

    alignSelf: "flex-start",

    paddingHorizontal: 12,

    paddingVertical: 7,

    borderRadius: 30,

    borderWidth: 1,

    borderColor: "rgba(255,255,255,0.15)",
  },

  text: {

    marginLeft: 6,

    fontSize: 12,

    fontWeight: "800",

    letterSpacing: 0.2,
  },

});