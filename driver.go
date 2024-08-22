package lang

import (
	"context"
	"fmt"
	"net"
	"os"
	"runtime/trace"

	"github.com/freeconf/lang/pb"
	"github.com/freeconf/yang/fc"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type Driver struct {
	listener net.Listener
	gserver  *grpc.Server
	pb.UnimplementedNodeServer
	xnodes      pb.XNodeClient
	xfs         pb.FileSystemClient
	handles     *HandlePool
	xclientAddr string
	Stats       DriverStats
}

type DriverStats struct {
	OpenNotifications int
}

func NewDriver(gServerAddr string, xClientAddr string) (*Driver, error) {
	trace.Log(context.Background(), "Driver", "Initializing new driver")
	d := &Driver{
		handles:     newHandlePool(),
		xclientAddr: xClientAddr,
	}
	trace.Log(context.Background(), "Driver", "Checking xClientAddr")
	// "" only useful for testing
	if xClientAddr != "" {
		trace.Log(context.Background(), "Driver", "Creating X Client")
		if err := d.createXClient(xClientAddr); err != nil {
			return nil, err
		}
	}
	trace.Log(context.Background(), "Driver", "Creating G Server")
	if err := d.createGServer(gServerAddr); err != nil {
		return nil, err
	}
	trace.Log(context.Background(), "Driver", "Driver initialization complete")
	return d, nil
}

func (d *Driver) createGServer(addr string) error {
	trace.Log(context.Background(), "Driver", fmt.Sprintf("Creating G Server at %s", addr))
	var err error
	if _, ferr := os.Stat(addr); ferr == nil {
		if err = os.Remove(addr); err != nil {
			trace.Log(context.Background(), "Driver", fmt.Sprintf("Failed to remove old socket: %s", err))
			return fmt.Errorf("could not remove old socket %s file. %w", addr, err)
		}
	}
	if d.listener, err = net.Listen("unix", addr); err != nil {
		trace.Log(context.Background(), "Driver", fmt.Sprintf("Failed to listen on %s: %s", addr, err))
		return fmt.Errorf("listen error. %s. %w", addr, err)
	}
	fc.Debug.Printf("started server on %s", addr)
	d.gserver = grpc.NewServer()
	pb.RegisterParserServer(d.gserver, &ParserService{d: d})
	pb.RegisterHandlesServer(d.gserver, &HandleService{d: d})
	pb.RegisterNodeServer(d.gserver, &NodeService{d: d})
	pb.RegisterNodeUtilServer(d.gserver, &NodeUtilService{d: d})
	pb.RegisterDeviceServer(d.gserver, &DeviceService{d: d})
	pb.RegisterProtoServer(d.gserver, &ProtoService{d: d})
	pb.RegisterFileSystemServer(d.gserver, &FileSystemService{d: d})
	trace.Log(context.Background(), "Driver", fmt.Sprintf("G Server created and listening at %s", addr))
	return nil
}

func (s *Driver) createXClient(addr string) error {
	trace.Log(context.Background(), "Driver", fmt.Sprintf("Creating X Client for address %s", addr))
	credentials := insecure.NewCredentials()
	dialer := func(ctx context.Context, addr string) (net.Conn, error) {
		var d net.Dialer
		return d.DialContext(ctx, "unix", addr)
	}
	options := []grpc.DialOption{
		grpc.WithTransportCredentials(credentials),
		grpc.WithBlock(),
		grpc.WithContextDialer(dialer),
	}
	channel, err := grpc.Dial(addr, options...)
	if err != nil {
		trace.Log(context.Background(), "Driver", fmt.Sprintf("Failed to connect to X Server at %s: %s", addr, err))
		return fmt.Errorf("failed to start client to x server on %s. %w", addr, err)
	}
	fc.Debug.Printf("connected to %s", addr)
	s.xnodes = pb.NewXNodeClient(channel)
	s.xfs = pb.NewFileSystemClient(channel)
	trace.Log(context.Background(), "Driver", fmt.Sprintf("X Client connected to %s", addr))
	return nil
}

// Serve is a blocking call that starts the GRPC server
func (s *Driver) Serve() error {
	trace.Log(context.Background(), "Driver", "Starting GRPC Server")
	defer s.listener.Close()
	if err := s.gserver.Serve(s.listener); err != nil {
		trace.Log(context.Background(), "Driver", fmt.Sprintf("GRPC Server error: %s", err))
		return fmt.Errorf("grpc server error. %w", err)
	}
	trace.Log(context.Background(), "Driver", "GRPC Server stopped")
	return nil
}

func (s *Driver) Stop() {
	trace.Log(context.Background(), "Driver", "Stopping GRPC Server")
	s.gserver.Stop()
	trace.Log(context.Background(), "Driver", "GRPC Server stopped")
}
