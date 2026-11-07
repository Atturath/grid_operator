## Introduction
As a system operator of a national grid, you have to control the following:

### Main challenges
The game has a short term (monthly) and medium term (annually) horizon.

For short term, you need to solve these challenge:
- **Ancillary service**: frequency support, FIR and SIR
- **Weather conditions**: cold snap, heat wave, strong wind that breaks infrastructure
- **Outage coordination**: some locations have transformer failure, etc, that means the danger of a casscading error
- **Economic shock**: increase of the fuel cost, or longer waiting time for the fuel

For medium term, you need to solve these challenge:
- **generation and load connection request**: check enough infrastructures, including protection schemes for inverter based technology
- You can choose the expensive schemes like full N-1 security, N security with demand response, etc.
- Are there enough base load?
- All the connection request comes with probability of cancelled connection.

The criteria of the win is security of supply + economic value, plus minimal nodal pricing difference.

### Starting configuration
It will start with five nodes: three residential, one industrial and one agriculture. The interconnection from the substations that supply the node also can be net supply or demand.

